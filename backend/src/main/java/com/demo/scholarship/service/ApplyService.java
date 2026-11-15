package com.demo.scholarship.service;

import com.demo.scholarship.common.ApiException;
import com.demo.scholarship.domain.Application;
import com.demo.scholarship.domain.Notice;
import com.demo.scholarship.domain.User;
import com.demo.scholarship.domain.enums.AppStatus;
import com.demo.scholarship.domain.enums.Role;
import com.demo.scholarship.repo.ApplicationRepository;
import com.demo.scholarship.repo.NoticeRepository;
import org.springframework.stereotype.Service;
import org.springframework.dao.DataIntegrityViolationException;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class ApplyService {

    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("yyyyMMdd");
    private static final DateTimeFormatter TIME = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    private final NoticeRepository noticeRepository;
    private final ApplicationRepository applicationRepository;

    public ApplyService(NoticeRepository noticeRepository, ApplicationRepository applicationRepository) {
        this.noticeRepository = noticeRepository;
        this.applicationRepository = applicationRepository;
    }

    public List<Map<String, Object>> listNotices() {
        LocalDateTime now = LocalDateTime.now();
        List<Map<String, Object>> result = new ArrayList<>();
        for (Notice notice : noticeRepository.findByPublishedTrueOrderByApplyEndDesc()) {
            result.add(noticeView(notice, now));
        }
        return result;
    }

    public Map<String, Object> getNotice(Long id) {
        Notice notice = noticeRepository.findByIdAndPublishedTrue(id)
                .orElseThrow(() -> new ApiException(404, "通知不存在或尚未发布"));
        return noticeView(notice, LocalDateTime.now());
    }

    private Map<String, Object> noticeView(Notice notice, LocalDateTime now) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("id", notice.getId());
        map.put("projectName", notice.getProjectName());
        map.put("batchName", notice.getBatchName());
        map.put("level", notice.getLevel());
        map.put("conditions", notice.getConditions());
        map.put("materials", MaskUtil.splitCsv(notice.getRequiredMaterials()));
        map.put("applyStart", notice.getApplyStart());
        map.put("applyEnd", notice.getApplyEnd());
        map.put("ended", !now.isBefore(notice.getApplyEnd()));
        map.put("open", !now.isBefore(notice.getApplyStart()) && now.isBefore(notice.getApplyEnd()));
        map.put("publicized", notice.isPublicized());
        map.put("publicityStart", notice.getPublicityStart());
        map.put("publicityEnd", notice.getPublicityEnd());
        return map;
    }

    public Map<String, Object> create(User student, Map<String, Object> body) {
        Long noticeId = asLong(body.get("noticeId"));
        if (noticeId == null) {
            throw new ApiException(400, "请选择申请项目");
        }
        Notice notice = noticeRepository.findByIdAndPublishedTrue(noticeId)
                .orElseThrow(() -> new ApiException(404, "通知不存在或尚未发布"));

        var existing = applicationRepository.findByStudentIdAndNoticeId(student.getId(), noticeId);
        if (existing.isPresent()) {
            return duplicateResult(existing.get());
        }

        LocalDateTime now = LocalDateTime.now();
        if (now.isBefore(notice.getApplyStart()) || !now.isBefore(notice.getApplyEnd())) {
            throw new ApiException(400, "当前不在申请开放时间内（" + format(notice.getApplyStart())
                    + " 至 " + format(notice.getApplyEnd()) + "）");
        }

        String reason = asText(body.get("reason"));
        if (reason.isBlank()) {
            throw new ApiException(400, "请填写申请理由");
        }

        List<String> required = MaskUtil.splitCsv(notice.getRequiredMaterials());
        List<String> submitted = asStringList(body.get("materials"));
        List<String> missing = new ArrayList<>(required);
        missing.removeAll(submitted);
        if (!missing.isEmpty()) {
            throw new ApiException(400, "缺少必需材料：" + String.join("、", missing));
        }

        Application app = new Application();
        app.setApplyNo("JZ" + now.format(DATE) + "-" + UUID.randomUUID().toString().substring(0, 6).toUpperCase());
        app.setStudentId(student.getId());
        app.setStudentName(student.getName());
        app.setStudentNo(student.getStudentNo());
        app.setCollege(student.getCollege());
        app.setCounselorId(student.getCounselorId());
        app.setNoticeId(notice.getId());
        app.setProjectName(notice.getProjectName());
        app.setBatchName(notice.getBatchName());
        app.setLevel(notice.getLevel());
        app.setReason(reason);
        app.setMaterials(String.join(",", submitted));
        app.setRequiredMaterials(notice.getRequiredMaterials());
        app.setStatus(AppStatus.PENDING_COUNSELOR);
        app.setSubmitTime(now);
        try {
            applicationRepository.saveAndFlush(app);
        } catch (DataIntegrityViolationException e) {
            return applicationRepository.findByStudentIdAndNoticeId(student.getId(), noticeId)
                    .map(ApplyService::duplicateResult)
                    .orElseThrow(() -> e);
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("duplicate", false);
        result.put("message", "提交成功，申请编号：" + app.getApplyNo());
        result.put("application", AppView.full(app));
        return result;
    }

    private static Map<String, Object> duplicateResult(Application app) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("duplicate", true);
        result.put("message", "该批次已提交过申请，返回原申请编号：" + app.getApplyNo());
        result.put("application", AppView.full(app));
        return result;
    }

    public List<Map<String, Object>> myApplications(User student) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Application app : applicationRepository.findByStudentIdOrderByIdDesc(student.getId())) {
            result.add(AppView.full(app));
        }
        return result;
    }

    public Map<String, Object> detail(User user, Long id) {
        Application app = load(id);
        boolean allowed;
        if (user.getRole() == Role.STUDENT) {
            allowed = app.getStudentId().equals(user.getId());
        } else if (user.getRole() == Role.COUNSELOR) {
            allowed = user.getId().equals(app.getCounselorId());
        } else if (user.getRole() == Role.COLLEGE) {
            allowed = user.getCollege() != null && user.getCollege().equals(app.getCollege());
        } else {
            allowed = true;
        }
        if (!allowed) {
            throw new ApiException(403, "无权查看该申请");
        }
        return AppView.full(app);
    }

    public Map<String, Object> resubmit(User student, Long id, Map<String, Object> body) {
        Application app = load(id);
        if (!app.getStudentId().equals(student.getId())) {
            throw new ApiException(403, "只能操作本人的申请");
        }
        if (app.getStatus() != AppStatus.RETURNED) {
            throw new ApiException(400, "当前状态不可重新提交");
        }
        LocalDateTime now = LocalDateTime.now();
        if (app.getCorrectionDeadline() != null && now.isAfter(app.getCorrectionDeadline())) {
            app.setStatus(AppStatus.CORRECTION_EXPIRED);
            app.setCorrectionExpiredAt(now);
            applicationRepository.save(app);
            throw new ApiException(400, "补正已截止，本轮申请终止");
        }

        String reason = asText(body.get("reason"));
        if (reason.isBlank()) {
            throw new ApiException(400, "请填写申请理由");
        }
        List<String> required = MaskUtil.splitCsv(app.getRequiredMaterials());
        List<String> submitted = asStringList(body.get("materials"));
        List<String> missing = new ArrayList<>(required);
        missing.removeAll(submitted);
        if (!missing.isEmpty()) {
            throw new ApiException(400, "缺少必需材料：" + String.join("、", missing));
        }

        app.setPrevMaterials(app.getMaterials());
        app.setReason(reason);
        app.setMaterials(String.join(",", submitted));
        app.setStatus(AppStatus.PENDING_COUNSELOR);
        applicationRepository.save(app);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("message", "重新提交成功，申请编号不变：" + app.getApplyNo());
        result.put("application", AppView.full(app));
        return result;
    }

    private Application load(Long id) {
        return applicationRepository.findById(id)
                .orElseThrow(() -> new ApiException(404, "申请不存在"));
    }

    static String format(LocalDateTime time) {
        return time == null ? "-" : time.format(TIME);
    }

    private static Long asLong(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (NumberFormatException e) {
            return null;
        }
    }

    static String asText(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    @SuppressWarnings("unchecked")
    static List<String> asStringList(Object value) {
        List<String> result = new ArrayList<>();
        if (value instanceof List<?> list) {
            for (Object item : list) {
                if (item != null && !String.valueOf(item).trim().isEmpty()) {
                    result.add(String.valueOf(item).trim());
                }
            }
        }
        return result;
    }
}
