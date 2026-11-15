package com.demo.scholarship.service;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class MaskUtilTest {
    @Test
    void masksNormalChineseNameAndStudentNumber() {
        assertEquals("王*明",MaskUtil.maskName("王小明"));
        assertEquals("********2026",MaskUtil.maskStudentNo("202411702026"));
    }

    @Test
    void masksShortOrMissingValues() {
        assertEquals("*",MaskUtil.maskName(null));
        assertEquals("*",MaskUtil.maskName("张"));
        assertEquals("***",MaskUtil.maskStudentNo("123"));
        assertTrue(MaskUtil.splitCsv(null).isEmpty());
    }
}
