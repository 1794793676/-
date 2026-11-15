package com.demo.scholarship.service;

import com.demo.scholarship.common.ApiException;
import com.demo.scholarship.domain.Application;
import com.demo.scholarship.domain.Notice;
import com.demo.scholarship.domain.User;
import com.demo.scholarship.domain.enums.AppStatus;
import com.demo.scholarship.repo.ApplicationRepository;
import com.demo.scholarship.repo.NoticeRepository;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class PublicityServiceTest {
    private final NoticeRepository notices = mock(NoticeRepository.class);
    private final ApplicationRepository applications = mock(ApplicationRepository.class);
    private final PublicityService service = new PublicityService(notices, applications);

    @Test
    void publishRejectsUnreviewedApplicationWithoutWriting() {
        Notice notice = new Notice(); notice.setId(10L);
        Application app = new Application(); app.setId(7L); app.setNoticeId(10L);
        app.setApplyNo("JZ-7"); app.setStatus(AppStatus.PENDING_COLLEGE);
        when(notices.findById(10L)).thenReturn(Optional.of(notice));
        when(applications.findById(7L)).thenReturn(Optional.of(app));
        ApiException error = assertThrows(ApiException.class, () -> service.publish(new User(),
                Map.of("noticeId",10,"start",LocalDateTime.now().toString(),
                        "end",LocalDateTime.now().plusDays(1).toString(),"applicationIds",List.of(7))));
        assertEquals(400, error.getStatus());
        assertFalse(notice.isPublicized());
        verify(notices, never()).save(any());
    }

    @Test
    void confirmRejectsBeforePublicityEnds() {
        Notice notice = new Notice(); notice.setId(10L); notice.setPublicized(true);
        notice.setPublicityEnd(LocalDateTime.now().plusDays(1));
        when(notices.findById(10L)).thenReturn(Optional.of(notice));
        ApiException error = assertThrows(ApiException.class, () -> service.confirm(new User(),10L,
                Map.of("disputeHandled",true,"items",List.of())));
        assertEquals(400,error.getStatus());
        verify(applications, never()).save(any());
    }
}
