package com.demo.scholarship.common;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class GlobalExceptionHandlerTest {
    @Test
    void internalExceptionDetailsAreNotExposed() {
        var response = new GlobalExceptionHandler().handleOther(new IllegalStateException("secret database detail"));
        assertEquals(500, response.getStatusCode().value());
        assertEquals("服务器处理失败", response.getBody().get("message"));
    }
}
