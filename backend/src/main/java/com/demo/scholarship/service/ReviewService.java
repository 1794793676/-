package com.demo.scholarship.service;

import com.demo.scholarship.common.ApiException;
import com.demo.scholarship.domain.Application;
import com.demo.scholarship.domain.User;
import com.demo.scholarship.domain.enums.AppStatus;
import com.demo.scholarship.repo.ApplicationRepository;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class ReviewService {

    private final ApplicationRepository applicationRepository;

    public ReviewService(ApplicationRepository applicationRepository) {
        this.applicationRepository = applicationRepository;
    }

    public List<Map<String, Object>> counselorApplications(User counselor) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Application app : applicationRepository.findByCounselorIdOrderByIdDesc(counselor.getId())) {
            result.add(AppView.full(app));
        }
        return result;
    }

    public Map<String, Object> counselorReview(User counselor, Long id, Map<String, Object> body) {
        Application app = load(id);
        if (!counselor.getId().equals(app.getCounselorId())) {
            throw new ApiException(403, "只能审核自己负责的学生申请");
        }
        if (app.getStatus() != AppStatus.PENDING_COUNSELOR) {
            throw new ApiException(400, "当前状态为“" + app.getStatus().getLabel() + "”，不能重复审核");
        }
        String action = ApplyService.asText(body.get("action"));
        String comment = ApplyService.asText(body.get("comment"));
        LocalDateTime now = LocalDateTime.now();

        if ("pass".equals(action)) {
            app.setCounselorOpinion(comment);
            app.setCounselorReviewedAt(now);
            app.setStatus(AppStatus.PENDING_COLLEGE);
        } else if ("reject".equals(action)) {
            if (comment.isBlank()) {
                throw new ApiException(400, "驳回时必须填写驳回理由");
            }
            app.setCounselorOpinion(comment);
            app.setCounselorReviewedAt(now);
            app.setStatus(AppStatus.REJECTED);
        } else {
            throw new ApiException(400, "审核动作无效");
        }
        applicationRepository.save(app);
        return result(app, "pass".equals(action) ? "审核通过，已送交学院复核" : "已驳回，本轮申请终止");
    }

    public Map<String, Object> correction(User counselor, Long id, Map<String, Object> body) {
        Application app = load(id);
        if (!counselor.getId().equals(app.getCounselorId())) {
            throw new ApiException(403, "只能操作自己负责的学生申请");
        }
        if (app.getStatus() != AppStatus.PENDING_COUNSELOR) {
            throw new ApiException(400, "当前状态为“" + app.getStatus().getLabel() + "”，不能发起退补");
        }
        String opinion = ApplyService.asText(body.get("opinion"));
        if (opinion.isBlank()) {
            throw new ApiException(400, "退补时必须填写补正意见");
        }
        String deadlineText = ApplyService.asText(body.get("deadline"));
        if (deadlineText.isBlank()) {
            throw new ApiException(400, "请设置补正截止时间");
        }
        LocalDateTime deadline;
        try {
            deadline = LocalDateTime.parse(deadlineText);
        } catch (DateTimeParseException e) {
            throw new ApiException(400, "补正截止时间格式不正确");
        }
        if (!deadline.isAfter(LocalDateTime.now())) {
            throw new ApiException(400, "补正截止时间必须晚于当前时间");
        }
        app.setCorrectionOpinion(opinion);
        app.setCorrectionDeadline(deadline);
        app.setStatus(AppStatus.RETURNED);
        applicationRepository.save(app);
        return result(app, "已退补，等待学生补正后重新提交");
    }

    public List<Map<String, Object>> collegeApplications(User reviewer) {
        List<Map<String, Object>> result = new ArrayList<>();
        if (reviewer.getCollege() == null) {
            return result;
        }
        for (Application app : applicationRepository.findByCollegeOrderByIdDesc(reviewer.getCollege())) {
            result.add(AppView.full(app));
        }
        return result;
    }

    public Map<String, Object> collegeReview(User reviewer, Long id, Map<String, Object> body) {
        Application app = load(id);
        if (reviewer.getCollege() == null || !reviewer.getCollege().equals(app.getCollege())) {
            throw new ApiException(403, "只能复核本学院的申请");
        }
        if (app.getStatus() != AppStatus.PENDING_COLLEGE) {
            throw new ApiException(400, "当前状态为“" + app.getStatus().getLabel() + "”，不能复核");
        }
        String action = ApplyService.asText(body.get("action"));
        String comment = ApplyService.asText(body.get("comment"));
        LocalDateTime now = LocalDateTime.now();

        if ("pass".equals(action)) {
            app.setCollegeOpinion(comment);
            app.setCollegeReviewedAt(now);
            app.setStatus(AppStatus.PENDING_PUBLICITY);
        } else if ("reject".equals(action)) {
            if (comment.isBlank()) {
                throw new ApiException(400, "驳回时必须填写驳回理由");
            }
            app.setCollegeOpinion(comment);
            app.setCollegeReviewedAt(now);
            app.setStatus(AppStatus.REJECTED);
        } else {
            throw new ApiException(400, "复核动作无效");
        }
        applicationRepository.save(app);
        return result(app, "pass".equals(action) ? "复核通过，已进入待公示" : "已驳回，本轮申请终止");
    }

    private Application load(Long id) {
        return applicationRepository.findById(id)
                .orElseThrow(() -> new ApiException(404, "申请不存在"));
    }

    private Map<String, Object> result(Application app, String message) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("message", message);
        map.put("application", AppView.full(app));
        return map;
    }
}
