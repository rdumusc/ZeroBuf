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


"""A C++ Function"""
class Function():
    def __init__(self, ret_val, function, body, static=False, explicit=False):
        self.ret_val = ret_val
        self.function = function
        self.body = body
        self.static = static
        self.explicit = explicit

    def write_declaration(self, file):
        if self.ret_val: # '{}'-less body
            file.write( "    {0}{1} {2};\n".
                          format( "static " if self.static else "", self.ret_val, self.function ))
        else:      # ctor '[initializer list]{ body }'
            file.write( "    {0}{1};\n".
                          format( "explicit " if self.explicit else "", self.function ))

    def write_implementation(self, file, classname):
        impl_function = re.sub(r" final$", "", self.function) # remove ' final' keyword
        impl_function = re.sub(r" = [0-9\.f]+ ", " ", impl_function) # remove default params

        if self.ret_val: # '{}'-less body
            file.write( "\n" + self.retVal + " " + classname +
                        "::" + impl_function + "\n{\n    " + self.body +
                        "\n}\n" )
        else:      # ctor '[initializer list]{ body }'
            file.write( "\n" + classname +
                        "::" + impl_function + "\n    " + self.body + "\n\n" )


"""A member of a C++ class"""
class ClassMember():
    def __init__(self, spec):
        self.cxxname = spec[0]
        self.cxxName = self.cxxname[0].upper() + self.cxxname[1:]
        self.cxxtype = emit.types[ spec[1] ][1]
        self.elemSize = emit.types[ spec[1] ][0]
        self.type = spec[2]
        self.functions = []
        self.fromJSON = ""
        self.toJSON = ""

    def write_declaration(self, file):
        for function in self.functions:
            function.write_declaration(file)
        file.write("\n")

    def write_implementation(self, file, classname):
        for function in self.functions:
            function.write_implementation(file, classname)
        file.write("\n")


"""A member of a class which has a fixed size (such as a POD type)"""
class StaticMember(ClassMember):
    def __init__(self, spec):
        super(StaticMember,self).__init__(spec)
        if len(spec) == 3:
            emit.defaultValues += "    set{0}({1}( {2} ));\n".\
                                  format(self.cxxName, self.cxxtype, self.type)

        if self.cxxtype in fbsFile.table_names:
            self.functions += Function( "const {0}&".format( self.cxxtype ),
                          "get" + cxxName + "() const",
                          "return _{0};".format( self.cxxname ))
            self.functions += Function( "{0}&".format( self.cxxtype ), "get" + self.cxxName + "()",
                          "notifyChanging();\n    " +
                          "return _{0};".format( cxxname ))
            self.functions += Function( "void",
                          "set"  + self.cxxName + "( const " + self.cxxtype + "& value )",
                          "notifyChanging();\n    " +
                          "_{0} = value;".format( self.cxxname ))
            self.fromJSON += "    ::zerobuf::fromJSON( ::zerobuf::getJSONField( json, \"{0}\" ), _{0} );\n".format(self.cxxname)
            self.toJSON += "    ::zerobuf::toJSON( static_cast< const ::zerobuf::Zerobuf& >( _{0} ), ::zerobuf::getJSONField( json, \"{0}\" ));\n".format(self.cxxname)
        else:
            self.functions += Function( cxxtype, "get" + cxxName + "() const",
                          "return getAllocator().template getItem< " + cxxtype +
                          " >( " + str( emit.offset ) + " );" )
            self.functions += Function( "void",
                          "set{0}( {1} value )".format(cxxName, cxxtype),
                          "notifyChanging();\n    " +
                          "getAllocator().template getItem< {0} >( {1} ) = value;".\
                          format(cxxtype, emit.offset) )

            self.fromJSON += "    set{0}( {1}( ::zerobuf::fromJSON< {2} >( ::zerobuf::getJSONField( json, \"{3}\" ))));\n".format(self.cxxName, self.cxxtype, "uint32_t" if self.cxxtype in emit.enums else self.cxxtype, self.cxxname)
            self.toJSON += "    ::zerobuf::toJSON( {0}( get{1}( )), ::zerobuf::getJSONField( json, \"{2}\" ));\n".format("uint32_t" if self.cxxtype in emit.enums else self.cxxtype, self.cxxName, self.cxxname)

    def get_initializer(self):
        return [self.cxxname, 1, self.cxxtype, emit.offset, self.elemSize]

    def get_member(self):
        return "{0} _{1};".format(self.cxxtype, self.cxxname)


"""A member of a class which is a fixed size array"""
class StaticMemberArray(ClassMember):
    def __init__(self, spec, classname):
        super(StaticMemberArray,self).__init__(spec)

        self.nElems = int( spec[4] )
        self.nBytes = self.elemSize * self.nElems

        if self.nElems < 2:
            sys.exit( "Static array of size {0} for field {1} not supported".
                      format(self.nElems, self.cxxname))
        if self.elemSize == 0:
            sys.exit( "Static array of {0} dynamic elements not implemented".
                      format(self.nElems))

        self.fromJSON += "    {\n"
        self.fromJSON += "        const Json::Value& field = ::zerobuf::getJSONField( json, \"{0}\" );\n".format(self.cxxname)
        self.toJSON += "    {\n"
        self.toJSON += "        Json::Value& field = ::zerobuf::getJSONField( json, \"{0}\" );\n".format(self.cxxname)

        if self.cxxtype in fbsFile.table_names:
            if self.elemSize == 0:
                sys.exit("Static arrays of empty ZeroBuf (field {0}) not supported".format(self.cxxname))

            self.functions += Function( "const {0}::{1}&".format( classname, self.cxxName ),
                          "get" + self.cxxName + "() const",
                          "return _{0};".format( self.cxxname ))
            self.functions += Function( "{0}::{1}&".format( classname, self.cxxName ),
                          "get" + cxxName + "()",
                          "notifyChanging();\n    " +
                          "return _{0};".format( self.cxxname ))
            self.functions += Function( "void",
                          "set{0}( const {0}& value )".format( self.cxxName ),
                          "notifyChanging();\n    " +
                          "_{0} = value;".format( self.cxxname ))

            for i in range(0, self.nElems):
                self.fromJSON += "        ::zerobuf::fromJSON( ::zerobuf::getJSONField( field, {1} ), _{0}[{1}] );\n".format(self.cxxname, i)
                self.toJSON += "        ::zerobuf::toJSON( static_cast< const ::zerobuf::Zerobuf& >( _{0}[{1}] ), ::zerobuf::getJSONField( field, {1} ));\n".format(self.cxxname, i)

        else:
            self.functions += Function( self.cxxtype + "*", "get" + self.cxxName + "()",
                          "notifyChanging();\n    " +
                          "return getAllocator().template getItemPtr< " + self.cxxtype +
                          " >( " + str( emit.offset ) + " );" )
            self.functions += Function( "const " + self.cxxtype + "*",
                          "get" + self.cxxName + "() const",
                          "return getAllocator().template getItemPtr< " + self.cxxtype +
                          " >( " + str( emit.offset ) + " );" )
            self.functions += Function( "std::vector< " + self.cxxtype + " >",
                          "get" + self.cxxName + "Vector() const",
                          "const " + self.cxxtype + "* ptr = getAllocator().template " +
                          "getItemPtr< " + self.cxxtype + " >( " + str( emit.offset ) +
                          " );\n    return std::vector< " + self.cxxtype +
                          " >( ptr, ptr + " + str( self.nElems ) + " );" )
            self.functions += Function( "void",
                          "set"  + self.cxxName + "( " + self.cxxtype + " value[ " +
                          self.nElems + " ] )",
                          "notifyChanging();\n    " +
                          "::memcpy( getAllocator().template getItemPtr< " +
                          cxxtype + " >( " + str( emit.offset ) + " ), value, " +
                          self.nElems + " * sizeof( " + self.cxxtype + " ));" )
            self.functions += Function( "void",
                          "set" + self.cxxName + "( const std::vector< " +
                          self.cxxtype + " >& value )",
                          "if( " + str( self.nElems ) + " >= value.size( ))\n" +
                          "    {\n" +
                          "        notifyChanging();" +
                          "        ::memcpy( getAllocator().template getItemPtr<" +
                          self.cxxtype + ">( " + str( emit.offset ) +
                          " ), value.data(), value.size() * sizeof( " + self.cxxtype +
                          "));\n" +
                          "    }" )
            self.functions += Function( "void",
                          "set" + self.cxxName + "( const std::string& value )",
                          "if( " + str( self.nBytes ) + " >= value.length( ))\n" +
                          "    {\n" +
                          "        notifyChanging();\n" +
                          "        ::memcpy( getAllocator().template getItemPtr<" +
                          self.cxxtype + ">( " + str( emit.offset ) +
                          " ), value.data(), value.length( ));\n" +
                          "    }" )

            self.fromJSON += "        {0}* array = ({0}*)get{1}();\n". \
                format("uint32_t" if self.cxxtype in emit.enums else self.cxxtype
                       , self.cxxName)
            self.toJSON += "        const {0}* array = (const {0}*)get{1}();\n". \
                format("uint32_t" if self.cxxtype in emit.enums else self.cxxtype,
                       self.cxxName)

            is_byte = self.type == "byte" or self.type == "ubyte"
            if is_byte:
                self.fromJSON += "        const std::string& decoded = ::zerobuf::fromJSONBinary( field );\n"
                self.fromJSON += "        ::memcpy( array, decoded.data(), std::min( decoded.length(), size_t( {0}ull )));\n".format(self.nElems)
                self.toJSON += "        ::zerobuf::toJSONBinary( array, {0}, field );\n".format(self.nElems)
            else:
                for i in range(0, self.nElems):
                    self.fromJSON += "        array[{0}] = ::zerobuf::fromJSON< {1} >( ::zerobuf::getJSONField( field, {0} ));\n".format(i, "uint32_t" if self.cxxtype in emit.enums else self.cxxtype)
                    self.toJSON += "        ::zerobuf::toJSON( array[{0}], ::zerobuf::getJSONField( field, {0} ));\n".format(i)

        self.functions += Function( "size_t", "get" + self.cxxName + "Size() const",
                      "return {0};".format(self.nElems))

        self.fromJSON += "    }\n"
        self.toJSON += "    }\n"

    def write_implementation(self, file, classname):
        file.write( "    typedef std::array< {0}, {1} > {2};\n".
                      format( self.cxxtype, self.nElems, self.cxxName ))
        super().write_implementation(file, classname)

    def get_initializer(self):
        return [self.cxxname, self.nElems, self.cxxtype, emit.offset, self.elemSize]

    def get_member(self):
        return "{0} _{1};".format(self.cxxName, self.cxxname)


"""A member of a class which has a dynamic size and is a ZeroBuf type"""
class DynamicZeroBufMember(ClassMember):
    def __init__(self, spec, dynamic_type_index):
        super(DynamicZeroBufMember,self).__init__(spec)
        self.dynamic_type_index = dynamic_type_index

        self.fromJSON = "    ::zerobuf::fromJSON( ::zerobuf::getJSONField( json, \"{0}\" ), _{0} );\n".format(self.cxxname)
        self.toJSON = "    ::zerobuf::toJSON( static_cast< const ::zerobuf::Zerobuf& >( _{0} ), ::zerobuf::getJSONField( json, \"{0}\" ));\n".format(self.cxxname)

        self.functions += Function("{0}&".format(self.cxxtype), "get{0}()".format(self.cxxName),
                                   "notifyChanging();\n    return _{0};".format(self.cxxname))
        self.functions += Function("const {0}&".format(self.cxxtype), "get{0}() const".format(self.cxxName),
                                   "return _{0};".format(self.cxxname))
        self.functions += Function("void", "set{0}( const {1}& value )".format(self.cxxName, self.cxxtype),
                                   "notifyChanging();\n    _{0} = value;".format(self.cxxname))

    def get_initializer(self):
        return [self.cxxname, 1, self.cxxtype, self.dynamic_type_index, 0]

    def get_member(self):
        return "{0} _{1};".format(self.cxxtype, self.cxxname)


"""A member of a class which has a dynamic size (vector type)"""
class DynamicMember(ClassMember):
    def __init__(self, spec, dynamic_type_index, classname):
        super(DynamicMember,self).__init__(spec)
        self.dynamic_type_index = dynamic_type_index
        self.isString = (spec[1] == "string")
        if self.isString:
            self.cxxtype = "char"
            self.elem_size = 1
        else:
            self.cxxtype = fbsFile.types[ self.type ][1]
            self.elem_size = fbsFile.types[ self.type ][0]
        self.isByte = self.type == "byte" or self.type == "ubyte"

        # JSON conversion
        if self.isString:
            self.fromJSON = "    set{0}( ::zerobuf::fromJSON< std::string >( ::zerobuf::getJSONField( json, \"{1}\" )));\n".format(self.cxxName, self.cxxname)
            self.toJSON = "    ::zerobuf::toJSON( get{0}String(), ::zerobuf::getJSONField( json, \"{1}\" ));\n".format(self.cxxName, self.cxxname)
        elif self.isByte:
            self.fromJSON = "    _{0}.fromJSONBinary( ::zerobuf::getJSONField( json, \"{0}\" ));\n".format(self.cxxname)
            self.toJSON = "    _{0}.toJSONBinary( ::zerobuf::getJSONField( json, \"{0}\" ));\n".format(self.cxxname)
        else:
            self.fromJSON = "    _{0}.fromJSON( ::zerobuf::getJSONField( json, \"{0}\" ));\n".format(self.cxxname)
            self.toJSON = "    _{0}.toJSON( ::zerobuf::getJSONField( json, \"{0}\" ));\n".format(self.cxxname)

        self.functions = []
        self.functions += Function( "{0}::{1}&".format( classname, self.cxxName ),
                                     "get" + cxxName + "()",
                                     "notifyChanging();\n    " +
                                     "return _{0};".format( self.cxxname ))
        self.functions += Function( "const {0}::{1}&".format( classname, self.cxxName ),
                                    "get" + self.cxxName + "() const",
                                    "return _{0};".format( self.cxxname ))

        if self.cxxtype in fbsFile.table_names: # Dynamic array of (static) Zerobufs
            if self.elem_size == 0:
                sys.exit("Dynamic arrays of empty ZeroBuf (field {0}) not supported".format(self.cxxname))

            self.functions += Function( "std::vector< " + self.cxxtype + " >",
                          "get" + self.cxxName + "Vector() const",
                          "const {0}& vec = get{0}();\n".format( self.cxxName ) +
                          "    std::vector< " + self.cxxtype + " > ret;\n" +
                          "    ret.reserve( vec.size( ));\n" +
                          "    for( size_t i = 0; i < vec.size(); ++i )\n" +
                          "        ret.push_back( vec[i] );\n" +
                          "    return ret;\n" )
            self.functions += Function( "void",
                          "set" + self.cxxName + "( const std::vector< " +
                          self.cxxtype + " >& values )",
                          "notifyChanging();\n    " +
                          "::zerobuf::Vector< {0} > dynamic( getAllocator(), {1} );\n".format(self.cxxtype, self.dynamic_type_index) +
                          "    dynamic.clear();\n" +
                          "    for( const " + self.cxxtype + "& data : values )\n" +
                          "        dynamic.push_back( data );" )

        else: # Dynamic array of PODs
            self.functions += Function( "void",
                          "set{0}( {1} const * value, size_t size )".\
                          format(self.cxxName, self.cxxtype),
                          "notifyChanging();\n    " +
                          "_copyZerobufArray( value, size * sizeof( " + self.cxxtype +
                          " ), " + str( self.dynamic_type_index ) + " );" )
            self.functions += Function( "std::vector< " + self.cxxtype + " >",
                          "get" + self.cxxName + "Vector() const",
                          "return std::vector< {0} >( _{1}.data(), _{1}.data() + _{1}.size( ));".format(self.cxxtype, self.cxxname))
            self.functions += Function( "void",
                          "set" + self.cxxName + "( const std::vector< " +
                          self.cxxtype + " >& value )",
                          "notifyChanging();\n    " +
                          "_copyZerobufArray( value.data(), value.size() * sizeof( " +
                          self.cxxtype + " ), " + str( self.dynamic_type_index ) + " );" )
            # string
            self.functions += Function( "std::string",
                          "get" + self.cxxName + "String() const",
                          "const uint8_t* ptr = getAllocator().template getDynamic< " +
                          "const uint8_t >( " + str( self.dynamic_type_index ) + " );\n" +
                          "    return std::string( ptr, ptr + " +
                          "getAllocator().template getItem< uint64_t >( " +
                          str( emit.offset + 8 ) + " ));" )
            self.functions += Function( "void",
                          "set" + self.cxxName + "( const std::string& value )",
                          "notifyChanging();\n    " +
                          "_copyZerobufArray( value.c_str(), value.length(), " +
                          str( self.dynamic_type_index ) + " );" )

    def get_initializer(self):
        return [self.cxxname, 0, self.cxxName, self.dynamic_type_index, self.elem_size]

    def get_member(self):
        return "{0} _{1};".format( cxxName, cxxname )

    def write_implementation(self, file, classname):
        file.write( "    typedef ::zerobuf::Vector< {0} > {1};\n".
                      format( self.cxxtype, self.cxxName ))
        super().write_implementation(file, classname)


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
    def __init__(self, item, namespace):
        self.name = item[1]
        self.attributes = item[2:]
        self.namespace = namespace
        self.offset = 4 # 4b version header in host endianness
        self.dynamic_members = []
        self.static_members = []
        self.zerobuf_types = set()
        self.functions = []
        self.functions += self.get_compact_function()
        self.initializers = []
        self.members = []

        self.fromJSON = ""
        self.toJSON = ""

        dynamic_type_index = 0
        for spec in self.attributes:
            if self.is_dynamic(spec):
                if len(spec) == 2 and spec[1] in fbsFile.table_names:
                    member = DynamicZeroBufMember(spec)
                    fbsFile.md5.update(member.cxxtype.encode('utf-8'))
                else:
                    member = DynamicMember(spec, dynamic_type_index, self.name)
                    fbsFile.md5.update(member.cxxtype.encode('utf-8') + b"Vector")

                self.offset += 16 # 8b offset, 8b size
                self.dynamic_members += member
                dynamic_type_index += 1
            else:
                if len(spec) == 2 or len(spec) == 3:
                    member = StaticMember(spec)
                    fbsFile.md5.update(member.cxxtype.encode('utf-8'))
                    self.offset += member.elemSize
                else:
                    member = StaticMemberArray(spec, self.name)
                    fbsFile.md5.update((member.cxxtype + str( member.nElems )).encode('utf-8'))
                    self.offset += member.nBytes
                self.static_members += member

            self.fromJSON += member.fromJSON
            self.toJSON += member.toJSON

            self.initializers.append(member.get_initializer())
            self.members.append(member.get_member())


        self.md5 = hashlib.md5()
        for namespace in self.namespace:
            self.md5.update(namespace.encode('utf-8') + b"::")
        self.md5.update(self.name.encode('utf-8'))

        if self.offset == 4: # OPT: table has no data
            self.offset = 0
            self.functions += Function(None, "{0}()".format( self.name ),
                         ": ::zerobuf::Zerobuf( ::zerobuf::AllocatorPtr( )){}")
            self.functions += Function(None,
                         "{0}( const {0}& )".format( self.name ),
                         ": ::zerobuf::Zerobuf( ::zerobuf::AllocatorPtr( )){}")
        else:
            # default ctor
            self.functions += Function(None, "{0}()".format(self.name),
                         ": {0}( ::zerobuf::AllocatorPtr( new ::zerobuf::NonMovingAllocator( {1}, {2} )))\n{{}}".format(self.name, self.offset, len(self.dynamic_members)))

            # member initialization ctor
            memberArgs = []
            initializers = ''
            for member in item[2:]:
                cxxname = member[0]
                cxxName = cxxname[0].upper() + cxxname[1:]
                if is_dynamic( member ):
                    isString = (member[1] == "string")
                    if isString:
                        cxxtype = "std::string"
                    elif(len(member) == 2 and member[1] in fbsFile.table_names):
                        # dynamic Zerobuf member
                        cxxtype = emit.types[member[1]][1]
                    else:
                        cxxtype = "std::vector< {0} >".format(emit.types[member[2]][1])
                else:
                    if len(member) == 2 or len(member) == 3:
                        cxxtype = emit.types[member[1]][1] # static member
                    else:
                        if member[2] in fbsFile.table_names:
                            cxxtype = cxxName # static array of zerobuf
                        else:
                            cxxtype = "std::vector< {0} >".format(emit.types[member[2]][1]) # static array of POD

                valueName = cxxname + 'Value'
                memberArgs.append("const {0}& {1}".format(cxxtype, valueName))
                initializers += "    set{0}( {1} );\n".format(cxxName, valueName)

            self.functions += Function( None,
                          "{0}( {1} )".format(self.name, ', '.join(memberArgs)),
                          ": {0}( ::zerobuf::AllocatorPtr( new ::zerobuf::NonMovingAllocator( {1}, {2} )))\n"
                          "{{\n{3}}}".format(self.name, self.offset, len(self.dynamic_members), initializers))

            # copy ctor
            self.functions += Function(None,
                         "{0}( const {0}& rhs )".format(self.name),
                         ": {0}( ::zerobuf::AllocatorPtr( new ::zerobuf::NonMovingAllocator( {1}, {2} )))\n".format(self.name, self.offset, len(self.dynamic_members)) +
                         "{\n    *this = rhs;\n}")

            # move ctor
            self.functions += Function(None,
                         "{0}( {0}&& rhs ) throw()".format(self.name),
                         ": ::zerobuf::Zerobuf( std::move( rhs ))\n" +
                         get_move_initializer(self))

            # copy-from-baseclass ctor
            self.functions += Function(None,
                         "{0}( const ::zerobuf::Zerobuf& rhs )".format(self.name),
                         ": {0}( ::zerobuf::AllocatorPtr( new ::zerobuf::NonMovingAllocator( {1}, {2} )))\n".format(self.name, self.offset, len(self.dynamic_members)) +
                         "{\n" +
                         "    ::zerobuf::Zerobuf::operator = ( rhs );\n" +
                         "}")

            # Zerobuf object owns allocator!
            self.functions += Function(None,
                         "{0}( ::zerobuf::AllocatorPtr allocator )".format( self.name ),
                         ": ::zerobuf::Zerobuf( std::move( allocator ))\n{0}".format(self.get_initializer_list()) +
                         "{{\n{3}}}".format(self.name, self.offset, len(self.dynamic_members), emit.defaultValues),
                         explicit = True)

            self.functions += Function("{0}&".format(self.name),
                         "operator = ( {0}&& rhs )".format(self.name),
                         "::zerobuf::Zerobuf::operator = ( std::move( rhs ));\n" +
                         get_move_operator(self) +
                         "    return *this;")
        if self.fromJSON:
            self.fromJSON = self.fromJSON[4:]
            self.toJSON = self.toJSON[4:]
            self.functions += Function( "void", "_parseJSON( const Json::Value& json ) final",
                          self.fromJSON )
            self.functions += Function( "void",
                          "_createJSON( Json::Value& json ) const final",
                          self.toJSON )

    def is_dynamic(self, spec):
        #  field is a sub-struct and field size is dynamic
        if spec[1] in fbsFile.table_names and fbsFile.types[spec[1]][0] == 0:
            return True

        if spec[1] == "string": # strings are dynamic
            return True

        if len(spec) == 4: # name : [type] dynamic array
            return True

        return False

    def get_offset(self):
        return self.offset if len(self.dynamic_members) == 0 else 0

    def write_declaration(self, file):
        self.write_class_begin(file)

        # member accessors
        for member in self.dynamic_members:
            member.write_declaration(file)
        for member in self.static_members:
            member.write_declaration(file)

        # ctors, dtor and assignment operator
        file.write("    virtual ~" + self.name + "() {}\n\n")
        if self.offset == 0: # OPT: table has no data
            file.write("    " + self.name + "& operator = ( const " +
                                self.name + "& ) { return *this; }\n\n")
        else:
            file.write("    " + self.name + "& operator = ( const " + self.name + "& rhs )\n"+
                       "        { ::zerobuf::Zerobuf::operator = ( rhs ); return *this; }\n\n")

        self.write_introspection(file)

        for function in self.functions:
            function.write_declaration(file)

        self.write_class_end(file)

    def write_class_begin(self, file):
        file.write( "class " + self.name + " : public ::zerobuf::Zerobuf\n" +
                    "{\npublic:\n" )

    def write_class_end(self, file):
        file.write( "private:\n    {0}\n".
                      format( '\n    '.join( emit.members )))
        file.write( "};\n\n" )

    def write_introspection(self, file):
        digest = self.md5.hexdigest()
        high = digest[ 0 : len( digest ) - 16 ]
        low  = digest[ len( digest ) - 16: ]
        zerobufType = "::zerobuf::uint128_t( 0x{0}ull, 0x{1}ull )".format( high,
                                                                           low )
        zerobufName = "{0}{1}{2}".format("::".join(self.namespace),
                                         "::" if self.namespace else "",
                                         self.name)
        file.write( "    // Introspection\n" )
        file.write( "    std::string getTypeName() const final {{ return \"{0}\"; }}\n".format( zerobufName ))
        file.write( "    ::zerobuf::uint128_t getTypeIdentifier() const final {{ return {0}; }}\n".format( zerobufType ))
        file.write( "    size_t getZerobufStaticSize() const final {{ return {0}; }}\n".format( self.offset ))
        file.write( "    static size_t ZEROBUF_STATIC_SIZE() {{ return {0}; }}\n".format( self.offset ))
        file.write( "    size_t getZerobufNumDynamics() const final {{ return {0}; }}\n".format( len(self.dynamic_members) ))
        file.write( "    static size_t ZEROBUF_NUM_DYNAMICS() {{ return {0}; }}\n".format( len(self.dynamic_members) ))
        file.write( "\n" )
        file.write( "\n" )

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
        if len(self.dynamic_members) > 0:
            compact = ''
            for dynamic_member in self.dynamic_members:
                compact += "    _{0}.compact( threshold );\n".format(dynamic_member.cxxname)
            compact += "    ::zerobuf::Zerobuf::compact( threshold );"
            compact = compact[4:]
            return Function("void", "compact( float threshold = 0.1f ) final", compact)


"""An fbs file which can be written to C++ header and implementation files."""
class FbsFile():
    def __init__(self, schema):
        self.generate_qobject = false
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
        self.enums += enum

    def add_table(self, item):
        table = FbsTable(item)
        self.tables += table
        self.table_names += table.name
        # record size in type lookup table, 0 if dynamically sized
        self.types[ table.name ] = ( table.get_offset(), table.name )

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

        write_namespace_opening(header)

        for enum in self.enums:
            enum.write_declaration(header)

        for table in self.tables:
            table.write_declaration(header)

        write_namespace_closing(header)

    """Write the C++ implementation file."""
    def write_implementation(self, cppsource):
        cppsource.write("#include <zerobuf/NonMovingAllocator.h>\n")
        cppsource.write("#include <zerobuf/NonMovingSubAllocator.h>\n")
        cppsource.write("#include <zerobuf/StaticSubAllocator.h>\n")
        cppsource.write("#include <zerobuf/json.h>\n")
        cppsource.write("\n")

        write_namespace_opening(cppsource)

        for table in self.tables:
            table.write_implementation(cppsource)

        write_namespace_closing(cppsource)

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
            cppsource.write( "#include \"{0}.h\"\n\n".format(headerbase) )

        schema = fbsObject.parseFile( file )
        # import pprint
        # pprint.pprint( schema.asList( ))
        fbsFile = FbsFile(schema)
        fbsFile.generate_qobject = args.qobject
        fbsFile.write_declaration(header)
        fbsFile.write_implementation(impl)

        if inline_implementation:
            header.write( "#include \"{0}.ipp\"\n\n".format(headerbase) )
