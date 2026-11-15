package com.demo.scholarship.repo;

import com.demo.scholarship.domain.Application;
import com.demo.scholarship.domain.enums.AppStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface ApplicationRepository extends JpaRepository<Application, Long> {

    Optional<Application> findByStudentIdAndNoticeId(Long studentId, Long noticeId);

    boolean existsByStudentIdAndNoticeId(Long studentId, Long noticeId);

    List<Application> findByStudentIdOrderByIdDesc(Long studentId);

    List<Application> findByCounselorIdOrderByIdDesc(Long counselorId);

    List<Application> findByCollegeOrderByIdDesc(String college);

    List<Application> findByNoticeIdOrderByIdAsc(Long noticeId);

    List<Application> findByNoticeIdAndStatusOrderByIdAsc(Long noticeId, AppStatus status);
}
