package com.demo.scholarship.service;

import com.demo.scholarship.common.ApiException;
import com.demo.scholarship.domain.Application;
import com.demo.scholarship.domain.Notice;
import com.demo.scholarship.domain.enums.AppStatus;
import com.demo.scholarship.repo.ApplicationRepository;
import com.demo.scholarship.repo.NoticeRepository;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class StatsService {

    private final NoticeRepository noticeRepository;
    private final ApplicationRepository applicationRepository;

    public StatsService(NoticeRepository noticeRepository, ApplicationRepository applicationRepository) {
        this.noticeRepository = noticeRepository;
        this.applicationRepository = applicationRepository;
    }

    public Map<String, Object> stats(Long noticeId, String college) {
        if (noticeId == null) {
            throw new ApiException(400, "请选择统计批次");
        }
        Notice notice = noticeRepository.findById(noticeId)
                .orElseThrow(() -> new ApiException(404, "批次不存在"));

        List<Application> apps = new ArrayList<>();
        for (Application app : applicationRepository.findByNoticeIdOrderByIdAsc(notice.getId())) {
            if (college == null || college.isBlank() || college.equals(app.getCollege())) {
                apps.add(app);
            }
        }

        Map<String, Map<String, Object>> groups = new LinkedHashMap<>();
        Map<AppStatus, Integer> overall = emptyCounts();
        int overallApproved = 0;

        for (Application app : apps) {
            String key = app.getProjectName() + "|" + app.getCollege();
            Map<String, Object> group = groups.computeIfAbsent(key, k -> {
                Map<String, Object> g = new LinkedHashMap<>();
                g.put("projectName", app.getProjectName());
                g.put("college", app.getCollege());
                g.put("total", 0);
                g.put("approved", 0);
                g.put("statusCounts", emptyLabels());
                return g;
            });
            increment(group, app.getStatus());
            overall.put(app.getStatus(), overall.get(app.getStatus()) + 1);
            if (app.getStatus() == AppStatus.APPROVED) {
                overallApproved++;
            }
        }

        List<Map<String, Object>> groupList = new ArrayList<>(groups.values());
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", apps.size());
        result.put("approved", overallApproved);
        result.put("statusCounts", statusMap(overall));
        result.put("groups", groupList);
        result.put("message", apps.isEmpty() ? "无匹配数据，各项统计为 0" : "统计完成");
        return result;
    }

    private void increment(Map<String, Object> group, AppStatus status) {
        group.put("total", (Integer) group.get("total") + 1);
        if (status == AppStatus.APPROVED) {
            group.put("approved", (Integer) group.get("approved") + 1);
        }
        @SuppressWarnings("unchecked")
        Map<String, Integer> counts = (Map<String, Integer>) group.get("statusCounts");
        counts.put(status.name(), counts.get(status.name()) + 1);
    }

    private Map<AppStatus, Integer> emptyCounts() {
        Map<AppStatus, Integer> map = new LinkedHashMap<>();
        for (AppStatus status : AppStatus.values()) {
            map.put(status, 0);
        }
        return map;
    }

    private Map<String, Integer> emptyLabels() {
        Map<String, Integer> map = new LinkedHashMap<>();
        for (AppStatus status : AppStatus.values()) {
            map.put(status.name(), 0);
        }
        return map;
    }

    private Map<String, Integer> statusMap(Map<AppStatus, Integer> counts) {
        Map<String, Integer> map = new LinkedHashMap<>();
        for (Map.Entry<AppStatus, Integer> entry : counts.entrySet()) {
            map.put(entry.getKey().name(), entry.getValue());
        }
        return map;
    }
}
