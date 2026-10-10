cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(hello_world)

# O Wokwi não simula as instruções SIMD do ESP32-S3 usadas pelo ESP-NN.
# Equivale a comentar "target_compile_options(... -DESP_NN)" no CMakeLists.txt do
# esp-tflite-micro, mas sem editar o componente baixado: sem -DESP_NN os kernels
# esp_nn/ caem nas implementações de referência do TFLite Micro.
idf_component_get_property(tflm_lib espressif__esp-tflite-micro COMPONENT_LIB)
get_target_property(tflm_opts ${tflm_lib} COMPILE_OPTIONS)
list(REMOVE_ITEM tflm_opts "-DESP_NN")
set_target_properties(${tflm_lib} PROPERTIES COMPILE_OPTIONS "${tflm_opts}")
