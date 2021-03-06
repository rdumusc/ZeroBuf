
/* Copyright (c) 2015-2016, Human Brain Project
 *                          Daniel Nachbaur <danielnachbaur@epfl.ch>
 */

#define BOOST_TEST_MODULE jsonSerialization

#include <boost/test/unit_test.hpp>
#include <iostream>

#include "serialization.h"

const std::string expectedNestedJson(
    "{\n"
    "   \"intvalue\" : 42,\n"
    "   \"uintvalue\" : 4200\n"
    "}\n");
const std::string expectedJson(
    "{\n"
    "   \"boolvalue\" : true,\n"
    "   \"bytearray\" : \"AQECAw==\",\n"
    "   \"bytedynamic\" : \"AQECAw==\",\n"
    "   \"bytevalue\" : 42,\n"
    "   \"doublearray\" : [ 1.0, 1.0, 2.0, 3.0 ],\n"
    "   \"doubledynamic\" : [ 1.0, 1.0, 2.0, 3.0 ],\n"
    "   \"doublevalue\" : 42.0,\n"
    "   \"enumarray\" : [ \"FIRST\", \"SECOND\" ],\n"
    "   \"enumdynamic\" : [ \"SECOND\", \"THIRD_UNDERSCORE\" ],\n"
    "   \"enumeration\" : \"SECOND\",\n"
    "   \"falseBool\" : false,\n"
    "   \"floatarray\" : [ 1.0, 1.0, 2.0, 3.0 ],\n"
    "   \"floatdynamic\" : [ 1.0, 1.0, 2.0, 3.0 ],\n"
    "   \"floatvalue\" : 42.0,\n"
    "   \"int16_tarray\" : [ 1, 1, 2, 3 ],\n"
    "   \"int16_tdynamic\" : [ 1, 1, 2, 3 ],\n"
    "   \"int16_tvalue\" : 42,\n"
    "   \"int32_tarray\" : [ 1, 1, 2, 3 ],\n"
    "   \"int32_tdynamic\" : [ 1, 1, 2, 3 ],\n"
    "   \"int32_tvalue\" : 42,\n"
    "   \"int64_tarray\" : [ 1, 1, 2, 3 ],\n"
    "   \"int64_tdynamic\" : [ 1, 1, 2, 3 ],\n"
    "   \"int64_tvalue\" : 42,\n"
    "   \"int8_tarray\" : [ 1, 1, 2, 3 ],\n"
    "   \"int8_tdynamic\" : [ 1, 1, 2, 3 ],\n"
    "   \"int8_tvalue\" : 42,\n"
    "   \"intarray\" : [ 1, 1, 2, 3 ],\n"
    "   \"intdynamic\" : [ 1, 1, 2, 3 ],\n"
    "   \"intvalue\" : 42,\n"
    "   \"nested\" : {\n"
    "      \"intvalue\" : 42,\n"
    "      \"uintvalue\" : 4200\n"
    "   },\n"
    "   \"nestedMember\" : {\n"
    "      \"intvalue\" : 7,\n"
    "      \"name\" : \"Hugo\"\n"
    "   },\n"
    "   \"nestedarray\" : [\n"
    "      {\n"
    "         \"intvalue\" : 42,\n"
    "         \"uintvalue\" : 4200\n"
    "      },\n"
    "      {\n"
    "         \"intvalue\" : 43,\n"
    "         \"uintvalue\" : 4201\n"
    "      },\n"
    "      {\n"
    "         \"intvalue\" : 44,\n"
    "         \"uintvalue\" : 4202\n"
    "      },\n"
    "      {\n"
    "         \"intvalue\" : 45,\n"
    "         \"uintvalue\" : 4203\n"
    "      }\n"
    "   ],\n"
    "   \"nesteddynamic\" : [\n"
    "      {\n"
    "         \"intvalue\" : 42,\n"
    "         \"uintvalue\" : 4200\n"
    "      },\n"
    "      {\n"
    "         \"intvalue\" : 43,\n"
    "         \"uintvalue\" : 4201\n"
    "      },\n"
    "      {\n"
    "         \"intvalue\" : 44,\n"
    "         \"uintvalue\" : 4202\n"
    "      },\n"
    "      {\n"
    "         \"intvalue\" : 45,\n"
    "         \"uintvalue\" : 4203\n"
    "      },\n"
    "      {\n"
    "         \"intvalue\" : 46,\n"
    "         \"uintvalue\" : 4204\n"
    "      },\n"
    "      {\n"
    "         \"intvalue\" : 47,\n"
    "         \"uintvalue\" : 4205\n"
    "      },\n"
    "      {\n"
    "         \"intvalue\" : 48,\n"
    "         \"uintvalue\" : 4206\n"
    "      },\n"
    "      {\n"
    "         \"intvalue\" : 49,\n"
    "         \"uintvalue\" : 4207\n"
    "      },\n"
    "      {\n"
    "         \"intvalue\" : 50,\n"
    "         \"uintvalue\" : 4208\n"
    "      },\n"
    "      {\n"
    "         \"intvalue\" : 51,\n"
    "         \"uintvalue\" : 4209\n"
    "      }\n"
    "   ],\n"
    "   \"shortarray\" : [ 1, 1, 2, 3 ],\n"
    "   \"shortdynamic\" : [ 1, 1, 2, 3 ],\n"
    "   \"shortvalue\" : 42,\n"
    "   \"stringvalue\" : \"testmessage\",\n"
    "   \"trueBool\" : true,\n"
    "   \"ubytearray\" : \"AQECAw==\",\n"
    "   \"ubytedynamic\" : \"AQECAw==\",\n"
    "   \"ubytevalue\" : 42,\n"
    "   \"uint128_tarray\" : [\n"
    "      {\n"
    "         \"high\" : 0,\n"
    "         \"low\" : 1\n"
    "      },\n"
    "      {\n"
    "         \"high\" : 0,\n"
    "         \"low\" : 1\n"
    "      },\n"
    "      {\n"
    "         \"high\" : 0,\n"
    "         \"low\" : 2\n"
    "      },\n"
    "      {\n"
    "         \"high\" : 0,\n"
    "         \"low\" : 3\n"
    "      }\n"
    "   ],\n"
    "   \"uint128_tdynamic\" : [\n"
    "      {\n"
    "         \"high\" : 0,\n"
    "         \"low\" : 1\n"
    "      },\n"
    "      {\n"
    "         \"high\" : 0,\n"
    "         \"low\" : 1\n"
    "      },\n"
    "      {\n"
    "         \"high\" : 0,\n"
    "         \"low\" : 2\n"
    "      },\n"
    "      {\n"
    "         \"high\" : 0,\n"
    "         \"low\" : 3\n"
    "      }\n"
    "   ],\n"
    "   \"uint128_tvalue\" : {\n"
    "      \"high\" : 0,\n"
    "      \"low\" : 42\n"
    "   },\n"
    "   \"uint16_tarray\" : [ 1, 1, 2, 3 ],\n"
    "   \"uint16_tdynamic\" : [ 1, 1, 2, 3 ],\n"
    "   \"uint16_tvalue\" : 42,\n"
    "   \"uint32_tarray\" : [ 1, 1, 2, 3 ],\n"
    "   \"uint32_tdynamic\" : [ 1, 1, 2, 3 ],\n"
    "   \"uint32_tvalue\" : 42,\n"
    "   \"uint64_tarray\" : [ 1, 1, 2, 3 ],\n"
    "   \"uint64_tdynamic\" : [ 1, 1, 2, 3 ],\n"
    "   \"uint64_tvalue\" : 42,\n"
    "   \"uint8_tarray\" : [ 1, 1, 2, 3 ],\n"
    "   \"uint8_tdynamic\" : [ 1, 1, 2, 3 ],\n"
    "   \"uint8_tvalue\" : 42,\n"
    "   \"uintarray\" : [ 1, 1, 2, 3 ],\n"
    "   \"uintdynamic\" : [ 1, 1, 2, 3 ],\n"
    "   \"uintvalue\" : 42,\n"
    "   \"ulongarray\" : [ 1, 1, 2, 3 ],\n"
    "   \"ulongdynamic\" : [ 1, 1, 2, 3 ],\n"
    "   \"ulongvalue\" : 42,\n"
    "   \"ushortarray\" : [ 1, 1, 2, 3 ],\n"
    "   \"ushortdynamic\" : [ 1, 1, 2, 3 ],\n"
    "   \"ushortvalue\" : 42\n"
    "}\n");

BOOST_AUTO_TEST_CASE(zerobufToJSON)
{
    const test::TestSchema& object(getTestObject());
    const std::string& json = object.toJSON();
    BOOST_CHECK_EQUAL(json, expectedJson);

    const test::TestNested& constNested = object.getNested();
    BOOST_CHECK_EQUAL(constNested.toJSON(), expectedNestedJson);

    test::TestNested nested = object.getNested();
    BOOST_CHECK_EQUAL(nested.toJSON(), expectedNestedJson);
}

BOOST_AUTO_TEST_CASE(zerobufFromJSON)
{
    test::TestNested nested;
    nested.fromJSON(expectedNestedJson);
    checkTestObject(nested);

    test::TestSchema object;
    object.fromJSON(expectedJson);
    checkTestObject(object);
}

BOOST_AUTO_TEST_CASE(zerobufFromPartialJSON)
{
    test::TestSchema object(getTestObject());
    BOOST_CHECK_EQUAL(object.getIntvalue(), 42);
    object.fromJSON("{ \"intvalue\" : 4242 }");
    BOOST_CHECK_EQUAL(object.getIntvalue(), 4242);

    // reset intvalue back and check no other value was modified
    object.setIntvalue(42);
    checkTestObject(object);

    // test shortening a vector
    object.fromJSON("{ \"ushortdynamic\" : [ 1, 1, 2 ] }");
    BOOST_CHECK_EQUAL(object.getUshortdynamic().size(), 3);
    BOOST_CHECK_EQUAL(object.getUshortdynamic()[2], 2);
}

// Before pull-request #71, updating a zerobuf object in a ZeroBuf vector was
// not possible if toJSON() was called before due to creating const Allocators
// for the vector objects.
BOOST_AUTO_TEST_CASE(zerobufVectorFromJSON)
{
    test::TestNestedZerobuf object;
    test::TestNested nested(1, 2);
    object.getNested().push_back(nested);

    std::string json = object.toJSON();
    object.getNested()[0].setIntvalue(5);

    BOOST_CHECK(object.fromJSON(json));
    BOOST_CHECK_EQUAL(object.getNested().size(), 1);
    BOOST_CHECK_EQUAL(object.getNested()[0].getIntvalue(), 1);
}

BOOST_AUTO_TEST_CASE(enum_string_conversion)
{
    test::TestEnum testEnum = test::TestEnum::FIRST;
    BOOST_CHECK_EQUAL(test::to_string(testEnum), "FIRST");
    testEnum = test::string_to_TestEnum("SECOND");
    BOOST_CHECK_EQUAL(testEnum, test::TestEnum::SECOND);
    BOOST_CHECK_NO_THROW(std::cout << testEnum << std::endl);

    BOOST_CHECK_THROW(test::string_to_TestEnum("wrong"), std::runtime_error);

    test::AnotherTestEnum anotherTestEnum = test::AnotherTestEnum::one;
    BOOST_CHECK_EQUAL(int(test::AnotherTestEnum::one), 1);
    BOOST_CHECK_EQUAL(int(test::AnotherTestEnum::three), 3);
    BOOST_CHECK_EQUAL(test::to_string(anotherTestEnum), "one");
    anotherTestEnum = test::string_to_AnotherTestEnum("three");
    BOOST_CHECK_EQUAL(anotherTestEnum, test::AnotherTestEnum::three);
    BOOST_CHECK_NO_THROW(std::cout << anotherTestEnum << std::endl);

    BOOST_CHECK_THROW(test::string_to_AnotherTestEnum("wrong"),
                      std::runtime_error);
}

BOOST_AUTO_TEST_CASE(json_schema_empty)
{
    const auto expected = R"({
    "$schema": "http://json-schema.org/schema#",
    "title": "TestEmpty",
    "description": "Class TestEmpty of namespace ['test']",
    "type": "object",
    "additionalProperties": false
})";
    BOOST_CHECK_EQUAL(test::TestEmpty::ZEROBUF_SCHEMA(), expected);
}

BOOST_AUTO_TEST_CASE(json_schema_nested)
{
    const auto expected = R"({
    "$schema": "http://json-schema.org/schema#",
    "title": "TestNested",
    "description": "Class TestNested of namespace ['test']",
    "type": "object",
    "additionalProperties": false,
    "properties": {
        "intvalue": {
            "type": "integer"
        },
        "uintvalue": {
            "type": "integer"
        }
    }
})";
    BOOST_CHECK_EQUAL(test::TestNested::ZEROBUF_SCHEMA(), expected);
}

BOOST_AUTO_TEST_CASE(json_schema_dynamic)
{
    const auto expected = R"({
    "$schema": "http://json-schema.org/schema#",
    "title": "TestDynamic",
    "description": "Class TestDynamic of namespace ['test']",
    "type": "object",
    "additionalProperties": false,
    "properties": {
        "intvalue": {
            "type": "integer"
        },
        "name": {
            "type": "string"
        }
    }
})";
    BOOST_CHECK_EQUAL(test::TestDynamic::ZEROBUF_SCHEMA(), expected);
}

BOOST_AUTO_TEST_CASE(json_schema_nested_zerobuf)
{
    const auto expected = R"({
    "$schema": "http://json-schema.org/schema#",
    "title": "TestNestedZerobuf",
    "description": "Class TestNestedZerobuf of namespace ['test']",
    "type": "object",
    "additionalProperties": false,
    "properties": {
        "nest": {
            "$schema": "http://json-schema.org/schema#",
            "title": "TestNested",
            "description": "Class TestNested of namespace ['test']",
            "type": "object",
            "additionalProperties": false,
            "properties": {
                "intvalue": {
                    "type": "integer"
                },
                "uintvalue": {
                    "type": "integer"
                }
            }
        },
        "dynamic": {
            "$schema": "http://json-schema.org/schema#",
            "title": "TestDynamic",
            "description": "Class TestDynamic of namespace ['test']",
            "type": "object",
            "additionalProperties": false,
            "properties": {
                "intvalue": {
                    "type": "integer"
                },
                "name": {
                    "type": "string"
                }
            }
        },
        "nested": {
            "type": "array",
            "items": {
                "$schema": "http://json-schema.org/schema#",
                "title": "TestNested",
                "description": "Class TestNested of namespace ['test']",
                "type": "object",
                "additionalProperties": false,
                "properties": {
                    "intvalue": {
                        "type": "integer"
                    },
                    "uintvalue": {
                        "type": "integer"
                    }
                }
            }
        }
    }
})";
    BOOST_CHECK_EQUAL(test::TestNestedZerobuf::ZEROBUF_SCHEMA(), expected);
}

BOOST_AUTO_TEST_CASE(json_schema_enum)
{
    const auto expected = R"({
    "$schema": "http://json-schema.org/schema#",
    "title": "TestEnumTable",
    "description": "Class TestEnumTable of namespace ['test']",
    "type": "object",
    "additionalProperties": false,
    "properties": {
        "value": {
            "$schema": "http://json-schema.org/schema#",
            "title": "TestEnum",
            "description": "Enum TestEnum of type uint",
            "type": "string",
            "additionalProperties": false,
            "enum": [
                "FIRST",
                "SECOND",
                "THIRD_UNDERSCORE"
            ]
        },
        "another": {
            "$schema": "http://json-schema.org/schema#",
            "title": "AnotherTestEnum",
            "description": "Enum AnotherTestEnum of type uint",
            "type": "string",
            "additionalProperties": false,
            "enum": [
                "one",
                "three"
            ]
        }
    }
})";
    BOOST_CHECK_EQUAL(test::TestEnumTable::ZEROBUF_SCHEMA(), expected);
}
