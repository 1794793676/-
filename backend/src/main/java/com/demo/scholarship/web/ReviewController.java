package com.demo.scholarship.web;

import com.demo.scholarship.domain.User;
import com.demo.scholarship.domain.enums.Role;
import com.demo.scholarship.service.AuthService;
import com.demo.scholarship.service.ReviewService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class ReviewController {

    private final ReviewService reviewService;
    private final AuthService authService;

    public ReviewController(ReviewService reviewService, AuthService authService) {
        this.reviewService = reviewService;
        this.authService = authService;
    }

    @GetMapping("/counselor/applications")
    public List<Map<String, Object>> counselorApplications(HttpServletRequest request) {
        User counselor = authService.requireRole(request, Role.COUNSELOR);
        return reviewService.counselorApplications(counselor);
    }

    @PostMapping("/applications/{id}/counselor-review")
    public Map<String, Object> counselorReview(@PathVariable Long id,
                                               @RequestBody Map<String, Object> body,
                                               HttpServletRequest request) {
        User counselor = authService.requireRole(request, Role.COUNSELOR);
        return reviewService.counselorReview(counselor, id, body);
    }

    @PostMapping("/applications/{id}/correction")
    public Map<String, Object> correction(@PathVariable Long id,
                                          @RequestBody Map<String, Object> body,
                                          HttpServletRequest request) {
        User counselor = authService.requireRole(request, Role.COUNSELOR);
        return reviewService.correction(counselor, id, body);
    }

    @GetMapping("/college/applications")
    public List<Map<String, Object>> collegeApplications(HttpServletRequest request) {
        User reviewer = authService.requireRole(request, Role.COLLEGE);
        return reviewService.collegeApplications(reviewer);
    }

    @PostMapping("/applications/{id}/college-review")
    public Map<String, Object> collegeReview(@PathVariable Long id,
                                             @RequestBody Map<String, Object> body,
                                             HttpServletRequest request) {
        User reviewer = authService.requireRole(request, Role.COLLEGE);
        return reviewService.collegeReview(reviewer, id, body);
    }
}
