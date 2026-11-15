package com.demo.scholarship.web;

import com.demo.scholarship.domain.User;
import com.demo.scholarship.domain.enums.Role;
import com.demo.scholarship.service.ApplyService;
import com.demo.scholarship.service.AuthService;
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
@RequestMapping("/api/applications")
public class ApplyController {

    private final ApplyService applyService;
    private final AuthService authService;

    public ApplyController(ApplyService applyService, AuthService authService) {
        this.applyService = applyService;
        this.authService = authService;
    }

    @PostMapping
    public Map<String, Object> create(@RequestBody Map<String, Object> body, HttpServletRequest request) {
        User student = authService.requireRole(request, Role.STUDENT);
        return applyService.create(student, body);
    }

    @GetMapping("/mine")
    public List<Map<String, Object>> mine(HttpServletRequest request) {
        User student = authService.requireRole(request, Role.STUDENT);
        return applyService.myApplications(student);
    }

    @GetMapping("/{id}")
    public Map<String, Object> detail(@PathVariable Long id, HttpServletRequest request) {
        User user = authService.require(request);
        return applyService.detail(user, id);
    }

    @PostMapping("/{id}/resubmit")
    public Map<String, Object> resubmit(@PathVariable Long id,
                                        @RequestBody Map<String, Object> body,
                                        HttpServletRequest request) {
        User student = authService.requireRole(request, Role.STUDENT);
        return applyService.resubmit(student, id, body);
    }
}
