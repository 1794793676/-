package com.demo.scholarship.service;

import com.demo.scholarship.common.ApiException;
import com.demo.scholarship.domain.Application;
import com.demo.scholarship.domain.Notice;
import com.demo.scholarship.domain.User;
import com.demo.scholarship.domain.enums.AppStatus;
import com.demo.scholarship.repo.ApplicationRepository;
import com.demo.scholarship.repo.NoticeRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class PublicityService {

    private final NoticeRepository noticeRepository;
    private final ApplicationRepository applicationRepository;

    public PublicityService(NoticeRepository noticeRepository, ApplicationRepository applicationRepository) {
        this.noticeRepository = noticeRepository;
        this.applicationRepository = applicationRepository;
    }

    public List<Map<String, Object>> candidates(Long noticeId) {
        Notice notice = loadNotice(noticeId);
        List<Map<String, Object>> result = new ArrayList<>();
        for (Application app : applicationRepository.findByNoticeIdOrderByIdAsc(notice.getId())) {
            result.add(AppView.full(app));
        }
        return result;
    }

    @Transactional
    public Map<String, Object> publish(User affairs, Map<String, Object> body) {
        Long noticeId = asLong(body.get("noticeId"));
        Notice notice = loadNotice(noticeId);

        LocalDateTime start = parseTime(body.get("start"), "公示开始时间");
        LocalDateTime end = parseTime(body.get("end"), "公示结束时间");
        if (start == null || end == null) {
            throw new ApiException(400, "请设置公示起止时间");
        }
        if (!end.isAfter(start)) {
            throw new ApiException(400, "公示结束时间必须晚于开始时间");
        }

        List<Long> ids = asLongList(body.get("applicationIds"));
        if (ids.isEmpty()) {
            throw new ApiException(400, "请选择要公示的记录");
        }

        List<Application> selected = new ArrayList<>();
        List<String> invalid = new ArrayList<>();
        for (Long id : ids) {
            Application app = applicationRepository.findById(id).orElse(null);
            if (app == null || !notice.getId().equals(app.getNoticeId())) {
                invalid.add("记录#" + id + "（不属于本批次）");
            } else if (app.getStatus() != AppStatus.PENDING_PUBLICITY) {
                invalid.add(app.getApplyNo() + "（" + app.getStatus().getLabel() + "）");
            } else {
                selected.add(app);
            }
        }
        if (!invalid.isEmpty()) {
            throw new ApiException(400, "以下记录不符合公示条件，已阻止整批发布：" + String.join("；", invalid));
        }

        notice.setPublicityStart(start);
        notice.setPublicityEnd(end);
        notice.setPublicized(true);
        noticeRepository.save(notice);

        for (Application app : selected) {
            app.setStatus(AppStatus.PUBLICIZING);
            applicationRepository.save(app);
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("message", "公示已发布，共 " + selected.size() + " 条记录进入公示中");
        result.put("count", selected.size());
        return result;
    }

    public Map<String, Object> maskedList(User user, Long noticeId) {
        Notice notice = loadNotice(noticeId);
        if (!notice.isPublicized()) {
            throw new ApiException(400, "该批次尚未发布公示");
        }
        List<Map<String, Object>> list = new ArrayList<>();
        for (Application app : applicationRepository.findByNoticeIdOrderByIdAsc(notice.getId())) {
            if (app.getStatus() == AppStatus.PUBLICIZING
                    || app.getStatus() == AppStatus.APPROVED
                    || app.getStatus() == AppStatus.REJECTED_UNSELECTED) {
                list.add(AppView.masked(app));
            }
        }
        Map<String, Object> result = noticeInfo(notice);
        result.put("list", list);
        return result;
    }

    public Map<String, Object> adminList(Long noticeId) {
        Notice notice = loadNotice(noticeId);
        if (!notice.isPublicized()) {
            throw new ApiException(400, "该批次尚未发布公示");
        }
        List<Map<String, Object>> list = new ArrayList<>();
        for (Application app : applicationRepository.findByNoticeIdOrderByIdAsc(notice.getId())) {
            list.add(AppView.full(app));
        }
        Map<String, Object> result = noticeInfo(notice);
        result.put("list", list);
        return result;
    }

    @Transactional
    public Map<String, Object> confirm(User affairs, Long noticeId, Map<String, Object> body) {
        Notice notice = loadNotice(noticeId);
        if (!notice.isPublicized()) {
            throw new ApiException(400, "该批次尚未发布公示");
        }
        LocalDateTime now = LocalDateTime.now();
        if (notice.getPublicityEnd() == null || now.isBefore(notice.getPublicityEnd())) {
            throw new ApiException(400, "公示期尚未结束，不能确认最终结果（结束时间："
                    + ApplyService.format(notice.getPublicityEnd()) + "）");
        }
        if (!Boolean.TRUE.equals(body.get("disputeHandled"))) {
            throw new ApiException(400, "请先确认线下异议处理已完成");
        }

        List<Application> publicizing = applicationRepository
                .findByNoticeIdAndStatusOrderByIdAsc(notice.getId(), AppStatus.PUBLICIZING);
        if (publicizing.isEmpty()) {
            throw new ApiException(400, "该批次没有处于公示中的记录");
        }

        List<Map<String, Object>> items = asMapList(body.get("items"));
        Map<Long, Map<String, Object>> itemMap = new HashMap<>();
        for (Map<String, Object> item : items) {
            Long appId = asLong(item.get("applicationId"));
            if (appId != null) {
                itemMap.put(appId, item);
            }
        }
        Set<Long> publicizingIds = new HashSet<>();
        for (Application app : publicizing) {
            publicizingIds.add(app.getId());
        }
        if (!itemMap.keySet().equals(publicizingIds)) {
            throw new ApiException(400, "必须覆盖该批次全部公示中记录，不允许遗漏或包含非公示中记录");
        }

        int approvedCount = 0;
        for (Application app : publicizing) {
            Map<String, Object> item = itemMap.get(app.getId());
            boolean approved = Boolean.TRUE.equals(item.get("approved"));
            String reason = ApplyService.asText(item.get("reason"));
            if (!approved && reason.isBlank()) {
                throw new ApiException(400, "未获批记录必须填写原因（申请编号：" + app.getApplyNo() + "）");
            }
            app.setStatus(approved ? AppStatus.APPROVED : AppStatus.REJECTED_UNSELECTED);
            app.setFinalReason(approved ? null : reason);
            app.setConfirmedAt(now);
            applicationRepository.save(app);
            if (approved) {
                approvedCount++;
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("message", "最终结果已确认：获批 " + approvedCount + " 人，未获批 "
                + (publicizing.size() - approvedCount) + " 人");
        result.put("approved", approvedCount);
        result.put("total", publicizing.size());
        return result;
    }

    private Map<String, Object> noticeInfo(Notice notice) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("noticeId", notice.getId());
        map.put("projectName", notice.getProjectName());
        map.put("batchName", notice.getBatchName());
        map.put("level", notice.getLevel());
        map.put("publicityStart", notice.getPublicityStart());
        map.put("publicityEnd", notice.getPublicityEnd());
        return map;
    }

    private Notice loadNotice(Long noticeId) {
        if (noticeId == null) {
            throw new ApiException(400, "请选择批次");
        }
        return noticeRepository.findById(noticeId)
                .orElseThrow(() -> new ApiException(404, "批次不存在"));
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

    private static LocalDateTime parseTime(Object value, String name) {
        String text = ApplyService.asText(value);
        if (text.isBlank()) {
            return null;
        }
        try {
            return LocalDateTime.parse(text);
        } catch (DateTimeParseException e) {
            throw new ApiException(400, name + "格式不正确");
        }
    }

    private static List<Long> asLongList(Object value) {
        List<Long> result = new ArrayList<>();
        if (value instanceof List<?> list) {
            for (Object item : list) {
                Long id = asLong(item);
                if (id != null) {
                    result.add(id);
                }
            }
        }
        return result;
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> asMapList(Object value) {
        List<Map<String, Object>> result = new ArrayList<>();
        if (value instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?> map) {
                    result.add((Map<String, Object>) map);
                }
            }
        }
        return result;
    }
}
