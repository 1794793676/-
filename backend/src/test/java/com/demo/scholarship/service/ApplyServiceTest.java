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

class ApplyServiceTest {
    private final NoticeRepository notices = mock(NoticeRepository.class);
    private final ApplicationRepository applications = mock(ApplicationRepository.class);
    private final ApplyService service = new ApplyService(notices, applications);

    @Test
    void duplicateSubmissionReturnsOriginalNumber() {
        Notice notice = new Notice(); notice.setId(10L);
        User student = new User(); student.setId(1L);
        Application old = new Application(); old.setId(7L); old.setApplyNo("JZ-OLD");
        old.setStatus(AppStatus.PENDING_COUNSELOR);
        when(notices.findByIdAndPublishedTrue(10L)).thenReturn(Optional.of(notice));
        when(applications.findByStudentIdAndNoticeId(1L, 10L)).thenReturn(Optional.of(old));
        Map<String,Object> result = service.create(student, Map.of("noticeId", 10));
        assertEquals(true, result.get("duplicate"));
        assertEquals("JZ-OLD", ((Map<?,?>) result.get("application")).get("applyNo"));
        verify(applications, never()).save(any());
    }

    @Test
    void missingRequiredMaterialIsRejected() {
        Notice notice = new Notice(); notice.setId(10L); notice.setRequiredMaterials("成绩单,申请表");
        notice.setApplyStart(LocalDateTime.now().minusDays(1));
        notice.setApplyEnd(LocalDateTime.now().plusDays(1));
        User student = new User(); student.setId(1L);
        when(notices.findByIdAndPublishedTrue(10L)).thenReturn(Optional.of(notice));
        when(applications.findByStudentIdAndNoticeId(1L,10L)).thenReturn(Optional.empty());
        ApiException error = assertThrows(ApiException.class, () -> service.create(student,
                Map.of("noticeId",10,"reason","申请理由","materials",List.of("成绩单"))));
        assertEquals(400, error.getStatus());
        assertTrue(error.getMessage().contains("申请表"));
        verify(applications, never()).save(any());
    }
}
