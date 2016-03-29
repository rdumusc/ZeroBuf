#!/usr/bin/env python

# TODO:
# * nested dynamic tables
# * endian swap method

# UUID is MD5 hash of namespace::namespace[<cxxtype>|<cxxtype>*|<cxxtype><size>]
# See @ref Binary for a description of the memory layout

import argparse
import hashlib
import re
from pyparsing import *
import sys
import os

fbsBaseType = oneOf( "int uint float double byte short ubyte ushort ulong uint8_t uint16_t " +
                     "uint32_t uint64_t uint128_t int8_t int16_t int32_t int64_t bool string" )

# namespace foo.bar
fbsNamespaceName = Group( ZeroOrMore( Word( alphanums ) + Suppress( '.' )) +
                          Word( alphanums ))
fbsNamespace = Group( Keyword( "namespace" ) + fbsNamespaceName +
                      Suppress( ';' ))

# enum EventDirection : ubyte { Subscriber, Publisher, Both }
fbsEnumValue = ( Word( alphanums+"_" ) + Suppress( Optional( ',' )))
fbsEnum = Group( Keyword( "enum" ) + Word( alphanums ) + Suppress( ':' ) +
                 fbsBaseType + Suppress( '{' ) + OneOrMore( fbsEnumValue ) +
                 Suppress( '}' ))

# value:[type] = defaultValue; entries in table
# TODO: support more default values other than numbers and booleans
fbsType = ( fbsBaseType ^ Word( alphanums ))
fbsTableArray = ( ( Literal( '[' ) + fbsType + Literal( ']' )) ^
                  ( Literal( '[' ) + fbsType + Literal( ':' ) + Word( nums ) +
                    Literal( ']' )) )
fbsTableValue = ((fbsType ^ fbsTableArray) + ZeroOrMore(Suppress('=') +
                Or([Word("true"), Word("false"), Word(nums+"-. ,")])))
fbsTableEntry = Group( Word( alphanums+"_" ) + Suppress( ':' ) + fbsTableValue +
                       Suppress( ';' ))
fbsTableSpec = ZeroOrMore( fbsTableEntry )

# table Foo { entries }
fbsTable = Group( Keyword( "table" ) + Word( alphas, alphanums ) +
                  Suppress( '{' ) + fbsTableSpec + Suppress( '}' ))

# root_type foo;
fbsRootType = Group( Keyword( "root_type" ) + Word( alphanums ) +
                     Suppress( ";" ))

# namespace, table(s), root_type
fbsItem = Or([fbsEnum, fbsTable])
fbsObject = ( Optional( fbsNamespace ) + OneOrMore( fbsItem ) +
              Optional( fbsRootType ))

fbsComment = cppStyleComment
fbsObject.ignore( fbsComment )

#fbsTableArray.setDebug()
#fbsTableValue.setDebug()
#fbsTableEntry.setDebug()


"""The value type of a C++ member"""
class ValueType():
    def __init__(self, type, size, is_zerobuf_type=False, is_byte_type=False):
        self.type = type
        self.size = size
        self.is_zerobuf_type = is_zerobuf_type
        self.is_byte_type = is_byte_type
        self.is_string = (type == "char*")
        if self.is_string:
            self.type = "char"
            self.size = 1

    def get_data_type(self):
        return "uint32_t" if self.is_zerobuf_type else self.type


"""A C++ Function"""
class Function():
    def __init__(self, ret_val, function, body, static=False, explicit=False, virtual=False):
        self.ret_val = ret_val
        self.function = function
        self.body = body
        self.static = "static " if static else ""
        self.explicit = "explicit " if explicit else ""
        self.virtual = "virtual " if virtual else ""

    def write_declaration(self, file):
        if self.ret_val: # '{}'-less body
            file.write( "    {0}{1} {2};\n".
                          format( self.static, self.ret_val, self.function ))
        else:      # ctor '[initializer list]{ body }'
            file.write( "    {0}{1}{2};\n".
                          format( self.virtual, self.explicit, self.function ))

    def write_implementation(self, file, classname):
        impl_function = re.sub(r" final$", "", self.function) # remove ' final' keyword
        impl_function = re.sub(r" = [0-9\.f]+ ", " ", impl_function) # remove default params

        if self.ret_val: # '{}'-less body
            file.write( "\n" + self.ret_val + " " + classname +
                        "::" + impl_function + "\n{\n    " + self.body +
                        "\n}\n" )
        else:      # ctor '[initializer list]{ body }'
            file.write( "\n" + classname +
                        "::" + impl_function + "\n    " + self.body + "\n\n" )


"""A member of a C++ class"""
class ClassMember():
    def __init__(self, name, value_type, allocator_offset):
        assert(isinstance(value_type, ValueType))
        self.cxxname = name
        self.cxxName = name[0].upper() + str(name[1:])
        self.value_type = value_type
        self.allocator_offset = allocator_offset
        self.functions = []

    def write_accessors_declaration(self, file):
        for function in self.functions:
            function.write_declaration(file)
        file.write("\n")

    def write_implementation(self, file, classname):
        for function in self.functions:
            function.write_implementation(file, classname)
        file.write("\n")

    def get_unique_identifier(self):
        return self.value_type.type.encode('utf-8')


"""A member of a class which has a fixed size (such as a POD type)"""
class FixedSizeMember(ClassMember):
    def __init__(self, name, type, allocator_offset):
        super(FixedSizeMember, self).__init__(name, type, allocator_offset)

        if self.value_type.is_zerobuf_type:
            self.functions.append(Function( "const {0}&".format( self.value_type.type ),
                          "get" + self.cxxName + "() const",
                          "return _{0};".format( self.cxxname )))
            self.functions.append(Function( "{0}&".format( self.value_type.type ), "get" + self.cxxName + "()",
                          "notifyChanging();\n    " +
                          "return _{0};".format( self.cxxname )))
            self.functions.append(Function( "void",
                          "set"  + self.cxxName + "( const " + self.value_type.type + "& value )",
                          "notifyChanging();\n    " +
                          "_{0} = value;".format( self.cxxname )))
        else:
            self.functions.append(Function(self.value_type.type, "get" + self.cxxName + "() const",
                          "return getAllocator().template getItem< " + self.value_type.type +
                          " >( " + str( allocator_offset ) + " );" ))
            self.functions.append(Function( "void",
                          "set{0}( {1} value )".format(self.cxxName, self.value_type.type),
                          "notifyChanging();\n    " +
                          "getAllocator().template getItem< {0} >( {1} ) = value;".\
                          format(self.value_type.type, allocator_offset)))

    def get_byte_size(self):
        return self.value_type.size

    def get_initializer(self):
        return [self.cxxname, 1, self.value_type.type, self.allocator_offset, self.value_type.size]

    def get_declaration(self):
        return "{0} _{1};".format(self.value_type.type, self.cxxname)

    def from_json(self):
        if self.value_type.is_zerobuf_type:
            return "    ::zerobuf::fromJSON( ::zerobuf::getJSONField( json, \"{0}\" ), _{0} );\n".format(self.cxxname)
        else:
            return "    set{0}( {1}( ::zerobuf::fromJSON< {2} >( ::zerobuf::getJSONField( json, \"{3}\" ))));\n".format(self.cxxName, self.value_type.type, self.value_type.get_data_type(), self.cxxname)

    def to_json(self):
        if self.value_type.is_zerobuf_type:
            return "    ::zerobuf::toJSON( static_cast< const ::zerobuf::Zerobuf& >( _{0} ), ::zerobuf::getJSONField( json, \"{0}\" ));\n".format(self.cxxname)
        else:
            return "    ::zerobuf::toJSON( {0}( get{1}( )), ::zerobuf::getJSONField( json, \"{2}\" ));\n".format(self.value_type.get_data_type(), self.cxxName, self.cxxname)


"""A member of a class which is a fixed size array"""
class FixedSizeMemberArray(ClassMember):
    def __init__(self, name, type, elem_count, classname, allocator_offset):
        super(FixedSizeMemberArray, self).__init__(name, type, allocator_offset)
        self.nElems = elem_count

        if self.nElems < 2:
            sys.exit( "Static array of size {0} for field {1} not supported".
                      format(self.nElems, self.cxxname))
        if self.value_type.size == 0:
            sys.exit( "Static array of {0} dynamic elements not implemented".
                      format(self.nElems))

        if self.value_type.is_zerobuf_type:
            if self.value_type.size == 0:
                sys.exit("Static arrays of empty ZeroBuf (field {0}) not supported".format(self.cxxname))

            self.functions.append(Function( "const {0}::{1}&".format( classname, self.cxxName ),
                          "get" + self.cxxName + "() const",
                          "return _{0};".format( self.cxxname )))
            self.functions.append(Function( "{0}::{1}&".format( classname, self.cxxName ),
                          "get" + self.cxxName + "()",
                          "notifyChanging();\n    " +
                          "return _{0};".format( self.cxxname )))
            self.functions.append(Function( "void",
                          "set{0}( const {0}& value )".format( self.cxxName ),
                          "notifyChanging();\n    " +
                          "_{0} = value;".format( self.cxxname )))
        else:
            self.functions.append(Function( self.value_type.type + "*", "get" + self.cxxName + "()",
                          "notifyChanging();\n    " +
                          "return getAllocator().template getItemPtr< " + self.value_type.type +
                          " >( " + str( allocator_offset ) + " );" ))
            self.functions.append(Function( "const " + self.value_type.type + "*",
                          "get" + self.cxxName + "() const",
                          "return getAllocator().template getItemPtr< " + self.value_type.type +
                          " >( " + str( allocator_offset ) + " );" ))
            self.functions.append(Function( "std::vector< " + self.value_type.type + " >",
                          "get" + self.cxxName + "Vector() const",
                          "const " + self.value_type.type + "* ptr = getAllocator().template " +
                          "getItemPtr< " + self.value_type.type + " >( " + str( allocator_offset ) +
                          " );\n    return std::vector< " + self.value_type.type +
                          " >( ptr, ptr + " + str( self.nElems ) + " );" ))
            self.functions.append(Function( "void",
                          "set"  + self.cxxName + "( " + self.value_type.type + " value[ " +
                          str(self.nElems) + " ] )",
                          "notifyChanging();\n    " +
                          "::memcpy( getAllocator().template getItemPtr< " +
                          self.value_type.type + " >( " + str( allocator_offset ) + " ), value, " +
                          str( self.nElems ) + " * sizeof( " + self.value_type.type + " ));" ))
            self.functions.append(Function( "void",
                          "set" + self.cxxName + "( const std::vector< " +
                          self.value_type.type + " >& value )",
                          "if( " + str( self.nElems ) + " >= value.size( ))\n" +
                          "    {\n" +
                          "        notifyChanging();" +
                          "        ::memcpy( getAllocator().template getItemPtr<" +
                          self.value_type.type + ">( " + str( allocator_offset ) +
                          " ), value.data(), value.size() * sizeof( " + self.value_type.type +
                          "));\n" +
                          "    }" ))
            self.functions.append(Function( "void",
                          "set" + self.cxxName + "( const std::string& value )",
                          "if( " + str(self.get_byte_size()) + " >= value.length( ))\n" +
                          "    {\n" +
                          "        notifyChanging();\n" +
                          "        ::memcpy( getAllocator().template getItemPtr<" +
                          self.value_type.type + ">( " + str( allocator_offset ) +
                          " ), value.data(), value.length( ));\n" +
                          "    }" ))

        self.functions.append(Function( "size_t", "get" + self.cxxName + "Size() const",
                      "return {0};".format(self.nElems)))

    def get_byte_size(self):
        return self.value_type.size * self.nElems

    def get_unique_identifier(self):
        return super().get_unique_identifier() + str(self.nElems).encode('utf-8')

    def write_accessors_declaration(self, file):
        if self.value_type.is_zerobuf_type:
            file.write( "    typedef std::array< {0}, {1} > {2};\n".
                          format( self.value_type.type, self.nElems, self.cxxName ))
        super().write_accessors_declaration(file)

    def get_initializer(self):
        return [self.cxxname, self.nElems, self.value_type.type, self.allocator_offset, self.value_type.size]

    def get_declaration(self):
        return "{0} _{1};".format(self.cxxName, self.cxxname)

    def from_json(self):
        fromJSON = "    {\n"
        fromJSON += "        const Json::Value& field = ::zerobuf::getJSONField( json, \"{0}\" );\n".format(self.cxxname)

        if self.value_type.is_zerobuf_type:
            for i in range(0, self.nElems):
                fromJSON += "        ::zerobuf::fromJSON( ::zerobuf::getJSONField( field, {1} ), _{0}[{1}] );\n".format(self.cxxname, i)
        else:
            fromJSON += "        {0}* array = ({0}*)get{1}();\n". \
                format(self.value_type.get_data_type(), self.cxxName)

            if self.value_type.is_byte_type:
                fromJSON += "        const std::string& decoded = ::zerobuf::fromJSONBinary( field );\n"
                fromJSON += "        ::memcpy( array, decoded.data(), std::min( decoded.length(), size_t( {0}ull )));\n".format(self.nElems)
            else:
                for i in range(0, self.nElems):
                    fromJSON += "        array[{0}] = ::zerobuf::fromJSON< {1} >( ::zerobuf::getJSONField( field, {0} ));\n".format(i, self.value_type.get_data_type())

        fromJSON += "    }\n"
        return fromJSON

    def to_json(self):
        toJSON = "    {\n"
        toJSON += "        Json::Value& field = ::zerobuf::getJSONField( json, \"{0}\" );\n".format(self.cxxname)

        if self.value_type.is_zerobuf_type:
            for i in range(0, self.nElems):
                toJSON += "        ::zerobuf::toJSON( static_cast< const ::zerobuf::Zerobuf& >( _{0}[{1}] ), ::zerobuf::getJSONField( field, {1} ));\n".format(self.cxxname, i)
        else:
            toJSON += "        const {0}* array = (const {0}*)get{1}();\n". \
                format(self.value_type.get_data_type(), self.cxxName)

            if self.value_type.is_byte_type:
                toJSON += "        ::zerobuf::toJSONBinary( array, {0}, field );\n".format(self.nElems)
            else:
                for i in range(0, self.nElems):
                    toJSON += "        ::zerobuf::toJSON( array[{0}], ::zerobuf::getJSONField( field, {0} ));\n".format(i)
        toJSON += "    }\n"
        return toJSON


"""A member of a class which has a dynamic size and is a ZeroBuf type"""
class DynamicZeroBufMember(ClassMember):
    def __init__(self, name, type, dynamic_type_index, allocator_offset):
        super(DynamicZeroBufMember,self).__init__(name, type, allocator_offset)
        self.dynamic_type_index = dynamic_type_index

        self.functions.append(Function("{0}&".format(self.value_type.type), "get{0}()".format(self.cxxName),
                                   "notifyChanging();\n    return _{0};".format(self.cxxname)))
        self.functions.append(Function("const {0}&".format(self.value_type.type), "get{0}() const".format(self.cxxName),
                                   "return _{0};".format(self.cxxname)))
        self.functions.append(Function("void", "set{0}( const {1}& value )".format(self.cxxName, self.value_type.type),
                                   "notifyChanging();\n    _{0} = value;".format(self.cxxname)))

    def get_byte_size(self):
        return 16 # 8b offset, 8b size

    def get_initializer(self):
        return [self.cxxname, 1, self.value_type.type, self.dynamic_type_index, 0]

    def get_declaration(self):
        return "{0} _{1};".format(self.value_type.type, self.cxxname)

    def from_json(self):
        return "    ::zerobuf::fromJSON( ::zerobuf::getJSONField( json, \"{0}\" ), _{0} );\n".format(self.cxxname)

    def to_json(self):
        return "    ::zerobuf::toJSON( static_cast< const ::zerobuf::Zerobuf& >( _{0} ), ::zerobuf::getJSONField( json, \"{0}\" ));\n".format(self.cxxname)


"""A member of a class which has a dynamic size (vector type)"""
class DynamicMember(ClassMember):
    def __init__(self, name, type, dynamic_type_index, classname, allocator_offset):
        super(DynamicMember, self).__init__(name, type, allocator_offset)
        self.dynamic_type_index = dynamic_type_index

        self.functions = []
        self.functions.append(Function( "{0}::{1}&".format( classname, self.cxxName ),
                                        "get" + self.cxxName + "()",
                                        "notifyChanging();\n    " +
                                        "return _{0};".format( self.cxxname )))
        self.functions.append(Function( "const {0}::{1}&".format( classname, self.cxxName ),
                                        "get" + self.cxxName + "() const",
                                        "return _{0};".format( self.cxxname )))

        if self.value_type.is_zerobuf_type: # Dynamic array of (static) Zerobufs
            if self.value_type.size == 0:
                sys.exit("Dynamic arrays of empty ZeroBuf (field {0}) not supported".format(self.cxxname))

            self.functions.append(Function( "std::vector< " + self.value_type.type + " >",
                                            "get" + self.cxxName + "Vector() const",
                                            "const {0}& vec = get{0}();\n".format( self.cxxName ) +
                                            "    std::vector< " + self.value_type.type + " > ret;\n" +
                                            "    ret.reserve( vec.size( ));\n" +
                                            "    for( size_t i = 0; i < vec.size(); ++i )\n" +
                                            "        ret.push_back( vec[i] );\n" +
                                            "    return ret;\n" ))
            self.functions.append(Function( "void",
                                            "set" + self.cxxName + "( const std::vector< " +
                                            self.value_type.type + " >& values )",
                                            "notifyChanging();\n    " +
                                            "::zerobuf::Vector< {0} > dynamic( getAllocator(), {1} );\n".format(self.value_type.type, self.dynamic_type_index) +
                                            "    dynamic.clear();\n" +
                                            "    for( const " + self.value_type.type + "& data : values )\n" +
                                            "        dynamic.push_back( data );" ))

        else: # Dynamic array of PODs
            self.functions.append(Function( "void",
                                            "set{0}( {1} const * value, size_t size )". \
                                            format(self.cxxName, self.value_type.type),
                                            "notifyChanging();\n    " +
                                            "_copyZerobufArray( value, size * sizeof( " + self.value_type.type +
                                            " ), " + str( self.dynamic_type_index ) + " );" ))
            self.functions.append(Function( "std::vector< " + self.value_type.type + " >",
                                            "get" + self.cxxName + "Vector() const",
                                            "return std::vector< {0} >( _{1}.data(), _{1}.data() + _{1}.size( ));".format(self.value_type.type, self.cxxname)))
            self.functions.append(Function( "void",
                                            "set" + self.cxxName + "( const std::vector< " +
                                            self.value_type.type + " >& value )",
                                            "notifyChanging();\n    " +
                                            "_copyZerobufArray( value.data(), value.size() * sizeof( " +
                                            self.value_type.type + " ), " + str( self.dynamic_type_index ) + " );" ))
            # string
            self.functions.append(Function( "std::string",
                                            "get" + self.cxxName + "String() const",
                                            "const uint8_t* ptr = getAllocator().template getDynamic< " +
                                            "const uint8_t >( " + str( self.dynamic_type_index ) + " );\n" +
                                            "    return std::string( ptr, ptr + " +
                                            "getAllocator().template getItem< uint64_t >( " +
                                            str( allocator_offset + 8 ) + " ));" ))
            self.functions.append(Function( "void",
                                            "set" + self.cxxName + "( const std::string& value )",
                                            "notifyChanging();\n    " +
                                            "_copyZerobufArray( value.c_str(), value.length(), " +
                                            str( self.dynamic_type_index ) + " );" ))

    def get_byte_size(self):
        return 16 # 8b offset, 8b size

    def get_unique_identifier(self):
        return super().get_unique_identifier() + b"Vector"

    def get_initializer(self):
        return [self.cxxname, 0, self.cxxName, self.dynamic_type_index, self.value_type.size]

    def get_declaration(self):
        return "{0} _{1};".format( self.cxxName, self.cxxname )

    def write_accessors_declaration(self, file):
        file.write( "    typedef ::zerobuf::Vector< {0} > {1};\n".
                      format( self.value_type.type, self.cxxName ))
        super().write_accessors_declaration(file)

    def from_json(self):
        if self.value_type.is_string:
            return "    set{0}( ::zerobuf::fromJSON< std::string >( ::zerobuf::getJSONField( json, \"{1}\" )));\n".format(self.cxxName, self.cxxname)
        elif self.value_type.is_byte_type:
            return "    _{0}.fromJSONBinary( ::zerobuf::getJSONField( json, \"{0}\" ));\n".format(self.cxxname)
        else:
            return "    _{0}.fromJSON( ::zerobuf::getJSONField( json, \"{0}\" ));\n".format(self.cxxname)

    def to_json(self):
        if self.value_type.is_string:
            return "    ::zerobuf::toJSON( get{0}String(), ::zerobuf::getJSONField( json, \"{1}\" ));\n".format(self.cxxName, self.cxxname)
        elif self.value_type.is_byte_type:
            return "    _{0}.toJSONBinary( ::zerobuf::getJSONField( json, \"{0}\" ));\n".format(self.cxxname)
        else:
            return "    _{0}.toJSON( ::zerobuf::getJSONField( json, \"{0}\" ));\n".format(self.cxxname)


"""An fbs enum which can be written as a C++ enum."""
class FbsEnum():
    def __init__(self, item):
        self.name = item[1]
        self.type = item[2]
        self.values = item[3:]

    def write_declaration(self, file):
        file.write( "enum " + self.name + "\n{\n" )
        for enumValue in self.values:
            file.write( "    " + self.name + "_" + enumValue + ",\n" )
        header.write( "};\n\n" )


"""An fbs Table (class) which can be written to a C++ implementation."""
class FbsTable():
    def __init__(self, item, namespace, fbsFile):
        self.name = item[1]
        self.attributes = item[2:]
        self.namespace = namespace
        self.offset = 4 # 4b version header in host endianness
        self.dynamic_members = []
        self.static_members = []
        self.zerobuf_types = set()
        self.functions = []
        self.initializers = []
        self.default_values = ""

        self.md5 = hashlib.md5()
        for namespace in self.namespace:
            self.md5.update(namespace.encode('utf-8') + b"::")
        self.md5.update(self.name.encode('utf-8'))

        dynamic_type_index = 0
        for spec in self.attributes:
            name = spec[0]
            fbs_type = spec[1] if len(spec) < 4 else spec[2]
            cxxtype = fbsFile.types[fbs_type][1]
            cxxtype_size = fbsFile.types[fbs_type][0]
            is_zerobuf_type = cxxtype in fbsFile.table_names
            is_byte_type = fbs_type == "byte" or fbs_type == "ubyte"
            value_type = ValueType(cxxtype, cxxtype_size, is_zerobuf_type, is_byte_type)

            if self.is_dynamic(spec, fbsFile):
                if len(spec) == 2 and is_zerobuf_type:
                    member = DynamicZeroBufMember(name, value_type, dynamic_type_index, self.offset)
                else:
                    member = DynamicMember(name, value_type, dynamic_type_index, self.name, self.offset)
                dynamic_type_index += 1
                self.dynamic_members.append(member)
            else:
                if len(spec) == 2 or len(spec) == 3:
                    member = FixedSizeMember(name, value_type, self.offset)
                    if len(spec) == 3:
                        default_values = spec[2]
                        self.default_values += "    set{0}({1}( {2} ));\n". \
                            format(member.cxxName, cxxtype, default_values)
                else:
                    elem_count = int(spec[4])
                    member = FixedSizeMemberArray(name, value_type, elem_count, self.name, self.offset)
                self.static_members.append(member)

            self.offset += member.get_byte_size()
            self.md5.update(member.get_unique_identifier())

        self.fill_initializer_list()

        if len(self.dynamic_members) > 0:
            self.functions.append(self.get_compact_function())

        if self.offset == 4: # OPT: table has no data
            self.offset = 0
            self.functions.append(Function(None, "{0}()".format( self.name ),
                         ": ::zerobuf::Zerobuf( ::zerobuf::AllocatorPtr( )){}"))
            self.functions.append(Function(None,
                         "{0}( const {0}& )".format( self.name ),
                         ": ::zerobuf::Zerobuf( ::zerobuf::AllocatorPtr( )){}"))
        else:
            # default ctor
            self.functions.append(Function(None, "{0}()".format(self.name),
                         ": {0}( ::zerobuf::AllocatorPtr( new ::zerobuf::NonMovingAllocator( {1}, {2} )))\n{{}}".format(self.name, self.offset, len(self.dynamic_members))))

            # member initialization ctor
            memberArgs = []
            initializers = ''
            for spec in self.attributes:
                cxxname = spec[0]
                cxxName = cxxname[0].upper() + cxxname[1:]
                cxxtype = self.get_cxxtype(spec, fbsFile)
                valueName = cxxname + 'Value'
                memberArgs.append("const {0}& {1}".format(cxxtype, valueName))
                initializers += "    set{0}( {1} );\n".format(cxxName, valueName)
            self.functions.append(Function( None,
                          "{0}( {1} )".format(self.name, ', '.join(memberArgs)),
                          ": {0}( ::zerobuf::AllocatorPtr( new ::zerobuf::NonMovingAllocator( {1}, {2} )))\n"
                          "{{\n{3}}}".format(self.name, self.offset, len(self.dynamic_members), initializers)))

            # copy ctor
            self.functions.append(Function(None,
                         "{0}( const {0}& rhs )".format(self.name),
                         ": {0}( ::zerobuf::AllocatorPtr( new ::zerobuf::NonMovingAllocator( {1}, {2} )))\n".format(self.name, self.offset, len(self.dynamic_members)) +
                         "{\n    *this = rhs;\n}"))

            # move ctor
            self.functions.append(Function(None,
                         "{0}( {0}&& rhs ) throw()".format(self.name),
                         ": ::zerobuf::Zerobuf( std::move( rhs ))\n" +
                         self.get_move_initializer()))

            # copy-from-baseclass ctor
            self.functions.append(Function(None,
                         "{0}( const ::zerobuf::Zerobuf& rhs )".format(self.name),
                         ": {0}( ::zerobuf::AllocatorPtr( new ::zerobuf::NonMovingAllocator( {1}, {2} )))\n".format(self.name, self.offset, len(self.dynamic_members)) +
                         "{\n" +
                         "    ::zerobuf::Zerobuf::operator = ( rhs );\n" +
                         "}"))

            # Zerobuf object owns allocator!
            self.functions.append(Function(None,
                         "{0}( ::zerobuf::AllocatorPtr allocator )".format( self.name ),
                         ": ::zerobuf::Zerobuf( std::move( allocator ))\n{0}".format(self.get_initializer_list()) +
                         "{{\n{3}}}".format(self.name, self.offset, len(self.dynamic_members), self.default_values),
                         explicit = True))

            # ctors, dtor and assignment operator
            self.functions.append(Function(None, "~" + self.name + "()", "{}", virtual=True))
            if self.offset == 0: # OPT: table has no data
                self.functions.append(Function(self.name+"&",
                                               "operator = ( const " + self.name + "& )",
                                               "{ return *this; }"))
            else:
                self.functions.append(Function(self.name+"&",
                                               "operator = ( const " + self.name + "& rhs )",
                                               "::zerobuf::Zerobuf::operator = ( rhs );\n" +
                                               "    return *this;"))

            self.functions.append(Function("{0}&".format(self.name),
                         "operator = ( {0}&& rhs )".format(self.name),
                         "::zerobuf::Zerobuf::operator = ( std::move( rhs ));\n" +
                         self.get_move_operator() +
                         "    return *this;"))

        # Introspection
        self.add_introspection_functions()

        # JSON
        self.add_json_functions()

    def add_introspection_functions(self):
        digest = self.md5.hexdigest()
        high = digest[ 0 : len( digest ) - 16 ]
        low  = digest[ len( digest ) - 16: ]
        zerobufType = "::zerobuf::uint128_t( 0x{0}ull, 0x{1}ull )".format( high, low )
        zerobufName = "{0}{1}{2}".format("::".join(self.namespace),
                                         "::" if self.namespace else "",
                                         self.name)

        self.functions.append(Function("std::string", "getTypeName() const final",
                                       "return \"{0}\";".format(zerobufName)))
        self.functions.append(Function("::zerobuf::uint128_t", "getTypeIdentifier() const final",
                                       "return {0};".format(zerobufType)))
        self.functions.append(Function("size_t", "getZerobufStaticSize() const final",
                                       "return {0};".format(self.offset)))
        self.functions.append(Function("size_t", "ZEROBUF_STATIC_SIZE()",
                                       "return {0};".format(self.offset), static=True))
        self.functions.append(Function("size_t", "getZerobufNumDynamics() const final",
                                       "return {0};".format(len(self.dynamic_members))))
        self.functions.append(Function("size_t", "ZEROBUF_NUM_DYNAMICS()",
                                       "return {0};".format(len(self.dynamic_members)), static=True))

    def add_json_functions(self):
        from_json = ""
        to_json = ""

        for member in self.dynamic_members:
            from_json += member.from_json()
            to_json += member.to_json()
        for member in self.static_members:
            from_json += member.from_json()
            to_json += member.to_json()

        if not from_json or not to_json:
            return

        from_json = from_json[4:]
        to_json = to_json[4:]
        self.functions.append(Function("void", "_parseJSON( const Json::Value& json ) final", from_json))
        self.functions.append(Function("void", "_createJSON( Json::Value& json ) const final", to_json))

    def is_dynamic(self, spec, fbsFile):
        #  field is a sub-struct and field size is dynamic
        if spec[1] in fbsFile.table_names and fbsFile.types[spec[1]][0] == 0:
            return True

        if spec[1] == "string": # strings are dynamic
            return True

        if len(spec) == 4: # name : [type] dynamic array
            return True

        return False

    def get_cxxtype(self, spec, fbsFile):
        fbs_type = spec[1] if len(spec) < 4 else spec[2]

        if self.is_dynamic(spec, fbsFile):
            if fbs_type == "string":
                cxxtype = "std::string"
            elif(len(spec) == 2 and fbs_type in fbsFile.table_names):
                # dynamic Zerobuf member
                cxxtype = fbsFile.types[fbs_type][1]
            else:
                cxxtype = "std::vector< {0} >".format(fbsFile.types[fbs_type][1])
        else:
            if len(spec) == 2 or len(spec) == 3:
                cxxtype = fbsFile.types[fbs_type][1] # static member
            else:
                if fbs_type in fbsFile.table_names:
                    #cxxtype = cxxName # static array of zerobuf
                    cxxtype = fbs_type # static array of zerobuf
                else:
                    cxxtype = "std::vector< {0} >".format(fbsFile.types[fbs_type][1]) # static array of POD
        return cxxtype

    def get_offset(self):
        return self.offset if len(self.dynamic_members) == 0 else 0

    def write_declaration(self, file):
        self.write_class_begin(file)

        # member accessors
        for member in self.dynamic_members:
            member.write_accessors_declaration(file)
        for member in self.static_members:
            member.write_accessors_declaration(file)

        for function in self.functions:
            function.write_declaration(file)

        self.write_class_end(file)

    def write_class_begin(self, file):
        file.write( "class " + self.name + " : public ::zerobuf::Zerobuf\n" +
                    "{\npublic:\n" )

    def write_class_end(self, file):
        member_declarations = []

        for member in self.dynamic_members:
            member_declarations.append(member.get_declaration())
        for member in self.static_members:
            if member.value_type.is_zerobuf_type:
                member_declarations.append(member.get_declaration())

        file.write( "private:\n    ")
        file.write( '\n    '.join(member_declarations))
        file.write( "\n};\n\n" )

    def write_implementation(self, file):
        # member access
        for member in self.dynamic_members:
            member.write_implementation(file, self.name)
        for member in self.static_members:
            member.write_implementation(file, self.name)
        for function in self.functions:
            function.write_implementation(file, self.name)

    def get_compact_function(self):
        # Recursive compaction
        compact = ''
        for dynamic_member in self.dynamic_members:
            compact += "    _{0}.compact( threshold );\n".format(dynamic_member.cxxname)
        compact += "    ::zerobuf::Zerobuf::compact( threshold );"
        compact = compact[4:]
        return Function("void", "compact( float threshold = 0.1f ) final", compact)

    def fill_initializer_list(self):
        # offset = 0
        for member in self.dynamic_members:
            self.initializers.append(member.get_initializer())
            # offset += member.get_byte_size()
        for member in self.static_members:
            if member.value_type.is_zerobuf_type:
                self.initializers.append(member.get_initializer())
            # offset += member.get_byte_size()

    def get_move_statics(self):
        movers = ''
        # [cxxname, nElems, cxxtype, offset|index, elemSize]
        for initializer in self.initializers:
            if initializer[1] == 1: # single member
                if initializer[4] == 0: # dynamic member
                    allocator = "::zerobuf::NonMovingSubAllocator( {{0}}, {0}, {1}::ZEROBUF_NUM_DYNAMICS(), {1}::ZEROBUF_STATIC_SIZE( ))".format(initializer[3], initializer[2])
                else:
                    allocator = "::zerobuf::StaticSubAllocator( {{0}}, {0}, {1} )".format(initializer[3], initializer[4])
                movers += "    _{0}.reset( ::zerobuf::AllocatorPtr( new {1}));\n"\
                    .format(initializer[0], allocator ).format( "getAllocator()" )
                movers += "    rhs._{0}.reset( ::zerobuf::AllocatorPtr( new {1}));\n"\
                    .format(initializer[0], allocator ).format( "rhs.getAllocator()" )
            elif initializer[1] != 0: # static array
                for i in range(0, initializer[1]):
                    movers += "    _{0}[{1}].reset( ::zerobuf::AllocatorPtr( "\
                        "new ::zerobuf::StaticSubAllocator( getAllocator(), {2}, {3} )));\n"\
                        .format(initializer[0], i, initializer[3], initializer[3] + i * initializer[4])
                    movers += "    rhs._{0}[{1}].reset( ::zerobuf::AllocatorPtr( "\
                        "new ::zerobuf::StaticSubAllocator( rhs.getAllocator(), {2}, {3} )));\n"\
                        .format(initializer[0], i, initializer[3], initializer[3] + i * initializer[4])
        return movers

    def get_move_operator(self):
        movers = ''
        # [cxxname, nElems, cxxtype, offset|index, elem_size]
        for initializer in self.initializers:
            if initializer[1] == 0: # dynamic array
                movers += "    _{0}.reset( getAllocator( ));\n".format(initializer[0])
                movers += "    rhs._{0}.reset( rhs.getAllocator( ));\n".format(initializer[0])
        movers += self.get_move_statics()
        return movers

    def get_move_initializer(self):
        initializers = ''
        # [cxxname, nElems, cxxtype, offset|index, elem_size]
        for initializer in self.initializers:
            if initializer[1] == 0: # dynamic array
                initializers += "    , _{0}( getAllocator(), {1} )\n".format(initializer[0], initializer[3])
        initializers += "{\n"
        initializers += self.get_move_operator()
        initializers += "}"
        return initializers

    def get_initializer_list(self):
        initializers = ''

        # [cxxname, nElems, cxxtype, offset, elem_size]
        for initializer in self.initializers:
            if initializer[1] == 0: # dynamic array
                initializers += "    , _{0}( getAllocator(), {1} )\n".format(initializer[0], initializer[3])
            elif initializer[1] == 1: # single member
                if initializer[4] == 0: # dynamic member
                    allocator = "::zerobuf::NonMovingSubAllocator( getAllocator(), {0}, {1}::ZEROBUF_NUM_DYNAMICS(), {1}::ZEROBUF_STATIC_SIZE( ))".format(initializer[3], initializer[2])
                else:
                    allocator = "::zerobuf::StaticSubAllocator( getAllocator(), {0}, {1} )".format(initializer[3], initializer[4])
                initializers += "    , _{0}( ::zerobuf::AllocatorPtr( new {1}))\n"\
                    .format(initializer[0], allocator)
            else: # static array
                initializers += "    , _{0}{1}".format(initializer[0], "{{")
                for i in range( 0, initializer[1] ):
                    initializers += "\n        {0}( ::zerobuf::AllocatorPtr( "\
                        "new ::zerobuf::StaticSubAllocator( getAllocator(), {1}, {2} ))){3} "\
                        .format(initializer[2], initializer[3] + i * initializer[4], initializer[4], "}}\n" if i == initializer[1] - 1 else ",")
        return initializers


"""An fbs file which can be written to C++ header and implementation files."""
class FbsFile():
    def __init__(self, schema):
        self.generate_qobject = False
        self.namespace = []
        self.enums = []
        self.tables = []
        self.table_names = set()
        # type lookup table: fbs type : ( size, C++ type )
        self.types = { "int" : ( 4, "int32_t" ),
                       "uint" : ( 4, "uint32_t" ),
                       "float" : ( 4, "float" ),
                       "double" : ( 8, "double" ),
                       "byte" : ( 1, "uint8_t" ),
                       "short" : ( 2, "int16_t" ),
                       "ubyte" : ( 1, "uint8_t" ),
                       "ushort" : ( 2, "uint16_t" ),
                       "ulong" : ( 8, "uint64_t" ),
                       "uint8_t" : ( 1, "uint8_t" ),
                       "uint16_t" : ( 2, "uint16_t" ),
                       "uint32_t" : ( 4, "uint32_t" ),
                       "uint64_t" : ( 8, "uint64_t" ),
                       "uint128_t" : ( 16, "::zerobuf::uint128_t" ),
                       "int8_t" : ( 1, "int8_t" ),
                       "int16_t" : ( 2, "int16_t" ),
                       "int32_t" : ( 4, "int32_t" ),
                       "int64_t" : ( 8, "int64_t" ),
                       "bool" : ( 1, "bool" ),
                       "string" : ( 1, "char*" )
                      }
        self.parse(schema)

    def parse(self, schema):
        """
        [['namespace', ['tide', 'rest']],
        ['enum', 'CommandType', 'uint', 'OpenContent', 'OpenWebbrowser'],
        ['table', 'Command', ['key', 'string'], ['value', 'string']],
        ['root_type', 'Command']]
        """
        root_options = { "namespace" : self.set_namespace,
                         "enum" : self.add_enum,
                         "table" : self.add_table,
                         "root_type" : self.set_root_type,
                        }
        for item in schema:
            root_options[ item[0] ]( item )

    def set_namespace(self, item):
        self.namespace = item[1]

    def add_enum(self, item):
        enum = FbsEnum(item)
        self.types[ enum.name ] = ( 4, enum.name )
        self.enums.append(enum)

    def add_table(self, item):
        table = FbsTable(item, self.namespace, self)
        self.tables.append(table)
        self.table_names.add(table.name)
        # record size in type lookup table, 0 if dynamically sized
        self.types[ table.name ] = ( table.get_offset(), table.name )

    def set_root_type(self, item):
        # Nothing to do with this statement
        return

    def write_namespace_opening(self, file):
        for namespace in self.namespace:
            file.write( "namespace " + namespace + "\n{\n" )

    def write_namespace_closing(self, file):
        for namespace in self.namespace:
            file.write( "}\n" )

    """Write the C++ header file."""
    def write_declaration(self, header):
        header.write( "// Generated by zerobufCxx.py\n\n" )
        header.write( "#pragma once\n" )
        header.write( "#include <zerobuf/Zerobuf.h> // base class\n" )
        header.write( "#include <zerobuf/Vector.h> // member\n" )
        header.write( "#include <array> // member\n" )
        header.write( "\n" )

        self.write_namespace_opening(header)

        for enum in self.enums:
            enum.write_declaration(header)

        for table in self.tables:
            table.write_declaration(header)

        self.write_namespace_closing(header)

    """Write the C++ implementation file."""
    def write_implementation(self, cppsource):
        cppsource.write("#include <zerobuf/NonMovingAllocator.h>\n")
        cppsource.write("#include <zerobuf/NonMovingSubAllocator.h>\n")
        cppsource.write("#include <zerobuf/StaticSubAllocator.h>\n")
        cppsource.write("#include <zerobuf/json.h>\n")
        cppsource.write("\n")

        self.write_namespace_opening(cppsource)

        for table in self.tables:
            table.write_implementation(cppsource)

        self.write_namespace_closing(cppsource)


if __name__ == "__main__":
    if len(sys.argv) < 2 :
        sys.exit("ERROR - " + sys.argv[0] + " - too few input arguments!")

    parser = argparse.ArgumentParser( description =
                                      "zerobufCxx.py: A zerobuf C++ code generator for extended flatbuffers schemas" )
    parser.add_argument( "files", nargs = "*" )
    parser.add_argument( '-o', '--outputdir', action='store', default = "",
                         help = "Prefix directory for all generated files.")
    parser.add_argument( '-e', '--extension', action='store', default = "cpp",
                         help = "Extension for generated source files.")
    parser.add_argument( '-q', '--qobject', action='store_true',
                         help = "Generate a QObject with signals and slots.")

    # Parse, interpret and validate arguments
    args = parser.parse_args()
    if len(args.files) == 0 :
        sys.exit("ERROR - " + sys.argv[0] + " - no input .fbs files given!")

    inline_implementation = args.extension == "ipp"

    for file in args.files:
        basename = os.path.splitext( file )[0]
        headerbase = os.path.basename( basename )
        if args.outputdir:
            if args.outputdir == '-':
                header = sys.stdout
                impl = sys.stdout
            else:
                if not os.path.exists( args.outputdir ):
                    os.makedirs( args.outputdir )
                header = open( args.outputdir + "/" + headerbase + ".h", 'w' )
                impl = open( args.outputdir + "/" + headerbase + "." + args.extension, 'w' )
        else:
            header = open( basename + ".h" , 'w' )
            impl = open( basename + "." + args.extension, 'w' )

        impl.write( "// Generated by zerobufCxx.py\n\n" )
        if not inline_implementation:
            impl.write( "#include \"{0}.h\"\n\n".format(headerbase) )

        schema = fbsObject.parseFile( file )
        # import pprint
        # pprint.pprint( schema.asList( ))
        fbsFile = FbsFile(schema)
        fbsFile.generate_qobject = args.qobject
        fbsFile.write_declaration(header)
        fbsFile.write_implementation(impl)

        if inline_implementation:
            header.write( "#include \"{0}.ipp\"\n\n".format(headerbase) )
