package com.demo.scholarship.web;

import com.demo.scholarship.domain.User;
import com.demo.scholarship.domain.enums.Role;
import com.demo.scholarship.service.AuthService;
import com.demo.scholarship.service.PublicityService;
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
@RequestMapping("/api/publicity")
public class PublicityController {

    private final PublicityService publicityService;
    private final AuthService authService;

    public PublicityController(PublicityService publicityService, AuthService authService) {
        this.publicityService = publicityService;
        this.authService = authService;
    }

    @GetMapping("/candidates/{noticeId}")
    public List<Map<String, Object>> candidates(@PathVariable Long noticeId, HttpServletRequest request) {
        authService.requireRole(request, Role.AFFAIRS);
        return publicityService.candidates(noticeId);
    }

    @PostMapping("/publish")
    public Map<String, Object> publish(@RequestBody Map<String, Object> body, HttpServletRequest request) {
        User affairs = authService.requireRole(request, Role.AFFAIRS);
        return publicityService.publish(affairs, body);
    }

    @GetMapping("/{noticeId}")
    public Map<String, Object> masked(@PathVariable Long noticeId, HttpServletRequest request) {
        User user = authService.require(request);
        return publicityService.maskedList(user, noticeId);
    }

    @GetMapping("/{noticeId}/admin")
    public Map<String, Object> adminList(@PathVariable Long noticeId, HttpServletRequest request) {
        authService.requireRole(request, Role.AFFAIRS);
        return publicityService.adminList(noticeId);
    }

    @PostMapping("/{noticeId}/confirm")
    public Map<String, Object> confirm(@PathVariable Long noticeId,
                                       @RequestBody Map<String, Object> body,
                                       HttpServletRequest request) {
        User affairs = authService.requireRole(request, Role.AFFAIRS);
        return publicityService.confirm(affairs, noticeId, body);
    }
}
