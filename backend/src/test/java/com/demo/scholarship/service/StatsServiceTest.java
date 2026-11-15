package com.demo.scholarship.service;

import com.demo.scholarship.domain.Application;
import com.demo.scholarship.domain.Notice;
import com.demo.scholarship.domain.enums.AppStatus;
import com.demo.scholarship.repo.ApplicationRepository;
import com.demo.scholarship.repo.NoticeRepository;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class StatsServiceTest {
    private final NoticeRepository notices = mock(NoticeRepository.class);
    private final ApplicationRepository applications = mock(ApplicationRepository.class);
    private final StatsService service = new StatsService(notices, applications);

    private void batch(Application... apps) {
        Notice notice = new Notice(); notice.setId(10L);
        when(notices.findById(10L)).thenReturn(Optional.of(notice));
        when(applications.findByNoticeIdOrderByIdAsc(10L)).thenReturn(List.of(apps));
    }

    @Test
    void countsApprovedAndOtherStatusesOncePerApplication() {
        Application approved = new Application(); approved.setProjectName("奖学金");
        approved.setCollege("计算机学院"); approved.setStatus(AppStatus.APPROVED);
        Application pending = new Application(); pending.setProjectName("奖学金");
        pending.setCollege("计算机学院"); pending.setStatus(AppStatus.PENDING_COLLEGE);
        batch(approved, pending);
        Map<String,Object> result = service.stats(10L, null);
        assertEquals(2, result.get("total"));
        assertEquals(1, result.get("approved"));
        assertEquals(1, ((Map<?,?>) result.get("statusCounts")).get("APPROVED"));
        assertEquals(1, ((List<?>) result.get("groups")).size());
    }

    @Test
    void collegeFilterWithNoMatchesReturnsZeroes() {
        Application app = new Application(); app.setCollege("计算机学院");
        app.setStatus(AppStatus.APPROVED); batch(app);
        Map<String,Object> result = service.stats(10L, "软件学院");
        assertEquals(0, result.get("total"));
        assertEquals(0, result.get("approved"));
        assertTrue(((List<?>) result.get("groups")).isEmpty());
    }
}
