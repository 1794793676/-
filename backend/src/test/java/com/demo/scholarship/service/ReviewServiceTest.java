package com.demo.scholarship.service;

import com.demo.scholarship.common.ApiException;
import com.demo.scholarship.domain.Application;
import com.demo.scholarship.domain.User;
import com.demo.scholarship.domain.enums.AppStatus;
import com.demo.scholarship.repo.ApplicationRepository;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ReviewServiceTest {
    private final ApplicationRepository applications = mock(ApplicationRepository.class);
    private final ReviewService service = new ReviewService(applications);

    private Application setup() {
        Application app = new Application(); app.setId(7L); app.setCounselorId(2L);
        app.setStatus(AppStatus.PENDING_COUNSELOR);
        when(applications.findById(7L)).thenReturn(Optional.of(app));
        return app;
    }

    @Test
    void counselorApprovalMovesApplicationToCollege() {
        Application app = setup(); User counselor = new User(); counselor.setId(2L);
        service.counselorReview(counselor,7L,Map.of("action","pass","comment","符合条件"));
        assertEquals(AppStatus.PENDING_COLLEGE,app.getStatus());
        assertNotNull(app.getCounselorReviewedAt());
        verify(applications).save(app);
    }

    @Test
    void counselorRejectionRequiresReason() {
        Application app = setup(); User counselor = new User(); counselor.setId(2L);
        ApiException error = assertThrows(ApiException.class, () ->
                service.counselorReview(counselor,7L,Map.of("action","reject","comment","")));
        assertEquals(400,error.getStatus());
        assertEquals(AppStatus.PENDING_COUNSELOR,app.getStatus());
        verify(applications,never()).save(any());
    }
}
