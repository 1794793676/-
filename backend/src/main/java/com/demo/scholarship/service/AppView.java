package com.demo.scholarship.service;

import com.demo.scholarship.domain.Application;

import java.util.LinkedHashMap;
import java.util.Map;

public final class AppView {

    private AppView() {
    }

    public static Map<String, Object> full(Application app) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("id", app.getId());
        map.put("applyNo", app.getApplyNo());
        map.put("studentId", app.getStudentId());
        map.put("studentName", app.getStudentName());
        map.put("studentNo", app.getStudentNo());
        map.put("college", app.getCollege());
        map.put("noticeId", app.getNoticeId());
        map.put("projectName", app.getProjectName());
        map.put("batchName", app.getBatchName());
        map.put("level", app.getLevel());
        map.put("reason", app.getReason());
        map.put("materials", MaskUtil.splitCsv(app.getMaterials()));
        map.put("requiredMaterials", MaskUtil.splitCsv(app.getRequiredMaterials()));
        map.put("status", app.getStatus().name());
        map.put("statusLabel", app.getStatus().getLabel());
        map.put("submitTime", app.getSubmitTime());
        map.put("counselorOpinion", app.getCounselorOpinion());
        map.put("counselorReviewedAt", app.getCounselorReviewedAt());
        map.put("collegeOpinion", app.getCollegeOpinion());
        map.put("collegeReviewedAt", app.getCollegeReviewedAt());
        map.put("finalReason", app.getFinalReason());
        map.put("confirmedAt", app.getConfirmedAt());
        map.put("correctionOpinion", app.getCorrectionOpinion());
        map.put("correctionDeadline", app.getCorrectionDeadline());
        map.put("prevMaterials", MaskUtil.splitCsv(app.getPrevMaterials()));
        map.put("correctionExpiredAt", app.getCorrectionExpiredAt());
        return map;
    }

    public static Map<String, Object> masked(Application app) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("id", app.getId());
        map.put("name", MaskUtil.maskName(app.getStudentName()));
        map.put("studentNo", MaskUtil.maskStudentNo(app.getStudentNo()));
        map.put("college", app.getCollege());
        map.put("projectName", app.getProjectName());
        map.put("batchName", app.getBatchName());
        map.put("level", app.getLevel());
        map.put("statusLabel", app.getStatus().getLabel());
        return map;
    }
}
