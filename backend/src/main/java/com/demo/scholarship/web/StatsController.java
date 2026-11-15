package com.demo.scholarship.web;

import com.demo.scholarship.service.AuthService;
import com.demo.scholarship.service.StatsService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import com.demo.scholarship.domain.enums.Role;

import java.util.Map;

@RestController
public class StatsController {

    private final StatsService statsService;
    private final AuthService authService;

    public StatsController(StatsService statsService, AuthService authService) {
        this.statsService = statsService;
        this.authService = authService;
    }

    @GetMapping("/api/stats")
    public Map<String, Object> stats(@RequestParam(required = false) String noticeId,
                                     @RequestParam(required = false) String college,
                                     HttpServletRequest request) {
        authService.requireRole(request, Role.AFFAIRS);
        Long id = null;
        if (noticeId != null && !noticeId.isBlank()) {
            try {
                id = Long.parseLong(noticeId);
            } catch (NumberFormatException e) {
                id = null;
            }
        }
        return statsService.stats(id, college);
    }
}
