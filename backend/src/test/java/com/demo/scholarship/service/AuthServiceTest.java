package com.demo.scholarship.service;

import com.demo.scholarship.common.ApiException;
import com.demo.scholarship.domain.User;
import com.demo.scholarship.domain.enums.Role;
import com.demo.scholarship.repo.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class AuthServiceTest {
    private final UserRepository users = mock(UserRepository.class);
    private final AuthService service = new AuthService(users);

    @Test
    void loginReturnsUserForCorrectPassword() {
        User user = new User();
        user.setId(1L); user.setUsername("zhang3"); user.setName("张三");
        user.setPassword("123456"); user.setRole(Role.STUDENT);
        when(users.findByUsername("zhang3")).thenReturn(Optional.of(user));
        assertEquals(1L, service.login(" zhang3 ", "123456").get("id"));
    }

    @Test
    void loginRejectsWrongPassword() {
        User user = new User(); user.setPassword("123456");
        when(users.findByUsername("zhang3")).thenReturn(Optional.of(user));
        ApiException error = assertThrows(ApiException.class,
                () -> service.login("zhang3", "bad"));
        assertEquals(401, error.getStatus());
    }

    @Test
    void requireRejectsMissingHeader() {
        ApiException error = assertThrows(ApiException.class,
                () -> service.require(new MockHttpServletRequest()));
        assertEquals(401, error.getStatus());
    }
}
