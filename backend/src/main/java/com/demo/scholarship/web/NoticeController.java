package com.demo.scholarship.web;

import com.demo.scholarship.service.ApplyService;
import com.demo.scholarship.service.AuthService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/notices")
public class NoticeController {

    private final ApplyService applyService;
    private final AuthService authService;

    public NoticeController(ApplyService applyService, AuthService authService) {
        this.applyService = applyService;
        this.authService = authService;
    }

    @GetMapping
    public List<Map<String, Object>> list(HttpServletRequest request) {
        authService.require(request);
        return applyService.listNotices();
    }

    @GetMapping("/{id}")
    public Map<String, Object> detail(@PathVariable Long id, HttpServletRequest request) {
        authService.require(request);
        return applyService.getNotice(id);
    }
}
