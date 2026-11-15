package com.demo.scholarship.domain;

import com.demo.scholarship.domain.enums.AppStatus;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import java.time.LocalDateTime;

@Entity
@Table(name = "applications",
        uniqueConstraints = @UniqueConstraint(columnNames = {"student_id", "notice_id"}))
public class Application {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private String applyNo;

    @Column(name = "student_id", nullable = false)
    private Long studentId;

    @Column(nullable = false)
    private String studentName;

    private String studentNo;

    private String college;

    private Long counselorId;

    @Column(name = "notice_id", nullable = false)
    private Long noticeId;

    private String projectName;

    private String batchName;

    private String level;

    @Column(length = 1000)
    private String reason;

    @Column(length = 1000)
    private String materials;

    @Column(length = 500)
    private String requiredMaterials;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private AppStatus status;

    private LocalDateTime submitTime;

    private String counselorOpinion;

    private LocalDateTime counselorReviewedAt;

    private String collegeOpinion;

    private LocalDateTime collegeReviewedAt;

    private String finalReason;

    private LocalDateTime confirmedAt;

    private String correctionOpinion;

    private LocalDateTime correctionDeadline;

    @Column(length = 1000)
    private String prevMaterials;

    private LocalDateTime correctionExpiredAt;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getApplyNo() {
        return applyNo;
    }

    public void setApplyNo(String applyNo) {
        this.applyNo = applyNo;
    }

    public Long getStudentId() {
        return studentId;
    }

    public void setStudentId(Long studentId) {
        this.studentId = studentId;
    }

    public String getStudentName() {
        return studentName;
    }

    public void setStudentName(String studentName) {
        this.studentName = studentName;
    }

    public String getStudentNo() {
        return studentNo;
    }

    public void setStudentNo(String studentNo) {
        this.studentNo = studentNo;
    }

    public String getCollege() {
        return college;
    }

    public void setCollege(String college) {
        this.college = college;
    }

    public Long getCounselorId() {
        return counselorId;
    }

    public void setCounselorId(Long counselorId) {
        this.counselorId = counselorId;
    }

    public Long getNoticeId() {
        return noticeId;
    }

    public void setNoticeId(Long noticeId) {
        this.noticeId = noticeId;
    }

    public String getProjectName() {
        return projectName;
    }

    public void setProjectName(String projectName) {
        this.projectName = projectName;
    }

    public String getBatchName() {
        return batchName;
    }

    public void setBatchName(String batchName) {
        this.batchName = batchName;
    }

    public String getLevel() {
        return level;
    }

    public void setLevel(String level) {
        this.level = level;
    }

    public String getReason() {
        return reason;
    }

    public void setReason(String reason) {
        this.reason = reason;
    }

    public String getMaterials() {
        return materials;
    }

    public void setMaterials(String materials) {
        this.materials = materials;
    }

    public String getRequiredMaterials() {
        return requiredMaterials;
    }

    public void setRequiredMaterials(String requiredMaterials) {
        this.requiredMaterials = requiredMaterials;
    }

    public AppStatus getStatus() {
        return status;
    }

    public void setStatus(AppStatus status) {
        this.status = status;
    }

    public LocalDateTime getSubmitTime() {
        return submitTime;
    }

    public void setSubmitTime(LocalDateTime submitTime) {
        this.submitTime = submitTime;
    }

    public String getCounselorOpinion() {
        return counselorOpinion;
    }

    public void setCounselorOpinion(String counselorOpinion) {
        this.counselorOpinion = counselorOpinion;
    }

    public LocalDateTime getCounselorReviewedAt() {
        return counselorReviewedAt;
    }

    public void setCounselorReviewedAt(LocalDateTime counselorReviewedAt) {
        this.counselorReviewedAt = counselorReviewedAt;
    }

    public String getCollegeOpinion() {
        return collegeOpinion;
    }

    public void setCollegeOpinion(String collegeOpinion) {
        this.collegeOpinion = collegeOpinion;
    }

    public LocalDateTime getCollegeReviewedAt() {
        return collegeReviewedAt;
    }

    public void setCollegeReviewedAt(LocalDateTime collegeReviewedAt) {
        this.collegeReviewedAt = collegeReviewedAt;
    }

    public String getFinalReason() {
        return finalReason;
    }

    public void setFinalReason(String finalReason) {
        this.finalReason = finalReason;
    }

    public LocalDateTime getConfirmedAt() {
        return confirmedAt;
    }

    public void setConfirmedAt(LocalDateTime confirmedAt) {
        this.confirmedAt = confirmedAt;
    }

    public String getCorrectionOpinion() {
        return correctionOpinion;
    }

    public void setCorrectionOpinion(String correctionOpinion) {
        this.correctionOpinion = correctionOpinion;
    }

    public LocalDateTime getCorrectionDeadline() {
        return correctionDeadline;
    }

    public void setCorrectionDeadline(LocalDateTime correctionDeadline) {
        this.correctionDeadline = correctionDeadline;
    }

    public String getPrevMaterials() {
        return prevMaterials;
    }

    public void setPrevMaterials(String prevMaterials) {
        this.prevMaterials = prevMaterials;
    }

    public LocalDateTime getCorrectionExpiredAt() {
        return correctionExpiredAt;
    }

    public void setCorrectionExpiredAt(LocalDateTime correctionExpiredAt) {
        this.correctionExpiredAt = correctionExpiredAt;
    }
}
