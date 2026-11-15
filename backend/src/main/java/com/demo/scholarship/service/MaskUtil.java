package com.demo.scholarship.service;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public final class MaskUtil {

    private MaskUtil() {
    }

    public static String maskName(String name) {
        if (name == null || name.isEmpty()) {
            return "*";
        }
        if (name.length() == 1) {
            return "*";
        }
        if (name.length() == 2) {
            return name.charAt(0) + "*";
        }
        return name.charAt(0) + "*".repeat(name.length() - 2) + name.charAt(name.length() - 1);
    }

    public static String maskStudentNo(String studentNo) {
        if (studentNo == null || studentNo.isEmpty()) {
            return "****";
        }
        if (studentNo.length() <= 4) {
            return "*".repeat(studentNo.length());
        }
        return "*".repeat(studentNo.length() - 4) + studentNo.substring(studentNo.length() - 4);
    }

    public static List<String> splitCsv(String value) {
        if (value == null || value.isBlank()) {
            return new ArrayList<>();
        }
        return Arrays.stream(value.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .toList();
    }
}
