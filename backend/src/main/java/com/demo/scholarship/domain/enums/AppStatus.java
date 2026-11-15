package com.demo.scholarship.domain.enums;

public enum AppStatus {
    PENDING_COUNSELOR("待辅导员审核"),
    PENDING_COLLEGE("待学院复核"),
    PENDING_PUBLICITY("待公示"),
    PUBLICIZING("公示中"),
    APPROVED("已获批"),
    REJECTED_UNSELECTED("未获批"),
    REJECTED("已驳回"),
    RETURNED("待补正"),
    CORRECTION_EXPIRED("补正逾期");

    private final String label;

    AppStatus(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }
}
