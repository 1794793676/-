package com.demo.scholarship.service;

import com.demo.scholarship.common.ApiException;
import com.demo.scholarship.domain.User;
import com.demo.scholarship.domain.enums.Role;
import com.demo.scholarship.repo.UserRepository;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class AuthService {

    private final UserRepository userRepository;

    public AuthService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    public Map<String, Object> login(String username, String password) {
        if (username == null || username.isBlank() || password == null || password.isBlank()) {
            throw new ApiException(400, "请输入账号和密码");
        }
        User user = userRepository.findByUsername(username.trim())
                .orElseThrow(() -> new ApiException(401, "账号或密码错误"));
        if (!user.getPassword().equals(password)) {
            throw new ApiException(401, "账号或密码错误");
        }
        return userInfo(user);
    }

    public User require(HttpServletRequest request) {
        String value = request.getHeader("X-User-Id");
        if (value == null || value.isBlank()) {
            throw new ApiException(401, "请先登录");
        }
        try {
            return userRepository.findById(Long.parseLong(value))
                    .orElseThrow(() -> new ApiException(401, "登录身份无效，请重新登录"));
        } catch (NumberFormatException e) {
            throw new ApiException(401, "登录身份无效，请重新登录");
        }
    }

    public User requireRole(HttpServletRequest request, Role role) {
        User user = require(request);
        if (user.getRole() != role) {
            throw new ApiException(403, "当前角色无权执行该操作");
        }
        return user;
    }

    public Map<String, Object> userInfo(User user) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("id", user.getId());
        map.put("username", user.getUsername());
        map.put("name", user.getName());
        map.put("role", user.getRole().name());
        map.put("studentNo", user.getStudentNo());
        map.put("college", user.getCollege());
        return map;
    }
}
