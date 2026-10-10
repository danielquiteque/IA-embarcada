idf_component_register(
    SRCS "main.cc" "mpu6050.c" "model.cc"
    INCLUDE_DIRS "."
    PRIV_REQUIRES esp_driver_i2c esp_driver_gpio esp_timer)
