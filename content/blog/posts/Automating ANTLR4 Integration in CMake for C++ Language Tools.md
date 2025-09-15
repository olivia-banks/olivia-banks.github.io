---
title: Automating ANTLR4 Integration in CMake for C++ Language Tools
date: 2023-03-06
type: page
description: Automatically managing ANTLR4 with CMake.
---
After the (personal) success of my last language, I decided to make a new one, but this time with more _modern_ tools. Goodbye C, hello C++! Goodbye, Lex/Yacc, hello ANTLR4! Of course, using ANTLR means I had to integrate it into CMake, since that's what I'm using. I found some people online who vendored in the source code, or manually included the ANTLR JAR (yuck!). I built a small CMake script to automate this, and I'll walk you through it here. If you want the code, jump to the bottom.

## Prelude
First things first, we need to inclue some things that we will need to fetch resources from the internet:

```cmake
find_package(Git REQUIRED)
find_package(Java 1.11 COMPONENTS Runtime REQUIRED)
include(FetchContent)
```

This, of course, requires the developer to have Git, at least JDK 11, and a CMake version modern enough for `FetchContent` to be a thing. This is pretty tame. The above code simply loads in Git and Java support into CMake, and includes a library for downloading (fetching) remote content.

## The Internet

There are two things we need to download: the ANTLR4 JAR, and the C++ runtime. Since the C++ runtime is built with CMake, we can include this easily, and the ANTLR4 JAR, being a single file, can be easily downloaded:

```cmake
# Download the ANTLR 4.13 JAR from the official website.
file(
  DOWNLOAD https://www.antlr.org/download/antlr-4.13.0-complete.jar
  EXPECTED_HASH SHA256=bc6f4abc0d225a27570126c51402569f000a8deda3487b70e7642840e570e4a6
  SHOW_PROGRESS
  ${CMAKE_BINARY_DIR}/antlr4.jar
)

# Fetch the ANTLR4 repository, and add ./runtime/Cpp as the CMake subdirectory.
set(FETCHCONTENT_QUIET FALSE)
FetchContent_Declare(
  antlr4cpp
  URL https://github.com/antlr/antlr4/archive/refs/tags/4.13.0.tar.gz
  URL_HASH SHA256=b7082b539256e6de5137a7d57afe89493dce234a3ce686dbae709ef6cf2d2c81
  DOWNLOAD_EXTRACT_TIMESTAMP true
)

set(ANTLR4CPP_JAR_LOCATION ${ANTLR4CPP_JAR_LOCATION})
option(ANTLR4CPP_JAR_LOCATION "Antlr4 CXX Jar Location" ${ANTLR4CPP_JAR_LOCATION})
set(BUILD_TESTS OFF)
option(BUILD_TESTS "Should tests be built?" OFF)
if(NOT antlr4cpp_POPULATED)
  FetchContent_Populate(antlr4cpp)
  add_subdirectory(${antlr4cpp_SOURCE_DIR}/runtime/Cpp ${antlr4cpp_BINARY_DIR})
endif()
```

## Wow, macros and functions!

Since every target wanting to use ANTLR from C++ has to link with the runtime, compile the `.g4` file into C++, compile it, link with it, include the correct headers, etc... it makes sense to provide some convenience functions.

```cmake
macro(antlr4cpp_process)
  set(one_value_args NAME)
  set(multi_value_args GRAMMARS)
  cmake_parse_arguments(ARGS "${options}" "${one_value_args}" "${multi_value_args}" ${ARGN})

  foreach(grammar ${ARGS_GRAMMARS})
	get_filename_component(grammar_name ${grammar} NAME_WE)
    set(out_prefix ${ANTLR4CPP_GENERATED_SRC_DIR}/${ARGS_NAME}/${grammar_name})

    set(antlr4cpp_generated_files_${ARGS_NAME} "")
    foreach(filename_postfix BaseListener BaseVisitor Lexer Listener Parser Visitor)
      list(APPEND antlr4cpp_generated_files_${ARGS_NAME} ${out_prefix}${filename_postfix}.cpp )
    endforeach()

    add_custom_command(
      OUTPUT ${antlr4cpp_generated_files_${ARGS_NAME}}
      COMMAND ${CMAKE_COMMAND} -E make_directory ${ANTLR4CPP_GENERATED_SRC_DIR}
      COMMAND "${Java_JAVA_EXECUTABLE}" -jar "${ANTLR4CPP_JAR_LOCATION}" -Werror -Dlanguage=Cpp -listener -visitor -o "${ANTLR4CPP_GENERATED_SRC_DIR}/${ARGS_NAME}" -package ${ARGS_NAME} "${ARGS_GRAMMARS}"
      WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
      DEPENDS ${ARGS_GRAMMARS}
    )
  endforeach()

  add_custom_target(
    antlr4cpp_generation_${ARGS_NAME}
    DEPENDS ${antlr4cpp_generated_files_${ARGS_NAME}}
  )

  # Export generated cpp files into list.
  foreach(generated_file ${antlr4cpp_generated_files_${ARGS_NAME}})
    list(APPEND antlr4cpp_src_files_${ARGS_NAME} ${generated_file})
  endforeach(generated_file)

  # Set include directory for generated sources.
  set(antlr4cpp_include_dirs_${ARGS_NAME} ${ANTLR4CPP_GENERATED_SRC_DIR}/${ARGS_NAME})
endmacro()
```

This next one is simpler, and just sets up an existing target so that it knows about ANTLR grammars and the whole runtime:

```cmake
function(target_link_antlr4)
  set(one_value_args TARGET)
  set(multi_value_args NAMES)
  cmake_parse_arguments(ARGS "${options}" "${one_value_args}" "${multi_value_args}" ${ARGN})

  # Link against every specified grammar, and the antlr4cpp runtime.
  target_include_directories(${ARGS_TARGET} PUBLIC ${ANTLR4CPP_INCLUDE_DIRS})
  target_link_libraries(${ARGS_TARGET} PUBLIC antlr4_static)
  foreach(name ${ARGS_NAMES})
    target_sources(${ARGS_TARGET} PUBLIC ${antlr4cpp_src_files_${name}})
    add_dependencies(${ARGS_TARGET} antlr4cpp_generation_${name})
    target_include_directories(${ARGS_TARGET} PUBLIC ${antlr4cpp_include_dirs_${name}})
  endforeach()
endfunction()
```

## The full code

```cmake
include(FetchContent)
find_package(Git REQUIRED)
find_package(Java 1.11 COMPONENTS Runtime REQUIRED)

file(
  DOWNLOAD https://www.antlr.org/download/antlr-4.13.0-complete.jar
  EXPECTED_HASH SHA256=bc6f4abc0d225a27570126c51402569f000a8deda3487b70e7642840e570e4a6
  SHOW_PROGRESS
  ${CMAKE_BINARY_DIR}/antlr4.jar
)

set(ANTLR4CPP_GENERATED_SRC_DIR ${CMAKE_BINARY_DIR}/antlr4cpp)
set(ANTLR4CPP_JAR_LOCATION ${CMAKE_BINARY_DIR}/antlr4.jar)
set(ANTLR4CPP_EXTERNAL_ROOT ${CMAKE_BINARY_DIR}/externals/antlr4cpp)
set(ANTLR4CPP_LOCAL_ROOT ${CMAKE_BINARY_DIR}/locals/antlr4cpp)
set(ANTLR4CPP_GENERATED_SRC_DIR ${CMAKE_BINARY_DIR}/antlr4cpp_sources)

set(FETCHCONTENT_QUIET FALSE)
FetchContent_Declare(
  antlr4cpp
  URL https://github.com/antlr/antlr4/archive/refs/tags/4.13.0.tar.gz
  URL_HASH SHA256=b7082b539256e6de5137a7d57afe89493dce234a3ce686dbae709ef6cf2d2c81
  DOWNLOAD_EXTRACT_TIMESTAMP true
)

set(ANTLR4CPP_JAR_LOCATION ${ANTLR4CPP_JAR_LOCATION})
option(ANTLR4CPP_JAR_LOCATION "Antlr4 CXX Jar Location" ${ANTLR4CPP_JAR_LOCATION})
set(BUILD_TESTS OFF)
option(BUILD_TESTS "Should tests be built?" OFF)
if(NOT antlr4cpp_POPULATED)
  FetchContent_Populate(antlr4cpp)
  add_subdirectory(${antlr4cpp_SOURCE_DIR}/runtime/Cpp ${antlr4cpp_BINARY_DIR})
endif()

list(APPEND ANTLR4CPP_INCLUDE_DIRS ${antlr4cpp_SOURCE_DIR}/runtime/Cpp/runtime/src)

function(target_link_antlr4)
  set(one_value_args TARGET)
  set(multi_value_args NAMES)
  cmake_parse_arguments(ARGS "${options}" "${one_value_args}" "${multi_value_args}" ${ARGN})

  # Link against every specified grammar, and the antlr4cpp runtime.
  target_include_directories(${ARGS_TARGET} PUBLIC ${ANTLR4CPP_INCLUDE_DIRS})
  target_link_libraries(${ARGS_TARGET} PUBLIC antlr4_static)
  foreach(name ${ARGS_NAMES})
    target_sources(${ARGS_TARGET} PUBLIC ${antlr4cpp_src_files_${name}})
    add_dependencies(${ARGS_TARGET} antlr4cpp_generation_${name})
    target_include_directories(${ARGS_TARGET} PUBLIC ${antlr4cpp_include_dirs_${name}})
  endforeach()
endfunction()

macro(antlr4cpp_process)
  set(one_value_args NAME)
  set(multi_value_args GRAMMARS)
  cmake_parse_arguments(ARGS "${options}" "${one_value_args}" "${multi_value_args}" ${ARGN})

  foreach(grammar ${ARGS_GRAMMARS})
    get_filename_component(grammar_name ${grammar} NAME_WE)
    set(out_prefix ${ANTLR4CPP_GENERATED_SRC_DIR}/${ARGS_NAME}/${grammar_name})

    set(antlr4cpp_generated_files_${ARGS_NAME} "")
    foreach(filename_postfix BaseListener BaseVisitor Lexer Listener Parser Visitor)
      list(APPEND antlr4cpp_generated_files_${ARGS_NAME} ${out_prefix}${filename_postfix}.cpp )
    endforeach()

    add_custom_command(
      OUTPUT ${antlr4cpp_generated_files_${ARGS_NAME}}
      COMMAND ${CMAKE_COMMAND} -E make_directory ${ANTLR4CPP_GENERATED_SRC_DIR}
      COMMAND "${Java_JAVA_EXECUTABLE}" -jar "${ANTLR4CPP_JAR_LOCATION}" -Werror -Dlanguage=Cpp -listener -visitor -o "${ANTLR4CPP_GENERATED_SRC_DIR}/${ARGS_NAME}" -package ${ARGS_NAME} "${ARGS_GRAMMARS}"
      WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
      DEPENDS ${ARGS_GRAMMARS}
    )
  endforeach()

  add_custom_target(
    antlr4cpp_generation_${ARGS_NAME}
    DEPENDS ${antlr4cpp_generated_files_${ARGS_NAME}}
  )

  # Export generated cpp files into list.
  foreach(generated_file ${antlr4cpp_generated_files_${ARGS_NAME}})
    list(APPEND antlr4cpp_src_files_${ARGS_NAME} ${generated_file})
  endforeach(generated_file)

  # Set include directory for generated sources.
  set(antlr4cpp_include_dirs_${ARGS_NAME} ${ANTLR4CPP_GENERATED_SRC_DIR}/${ARGS_NAME})
endmacro()
```
