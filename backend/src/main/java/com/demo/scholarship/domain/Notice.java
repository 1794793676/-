package com.demo.scholarship.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.LocalDateTime;

@Entity
@Table(name = "notices")
public class Notice {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String projectName;

    @Column(nullable = false)
    private String batchName;

    private String level;

    @Column(length = 1000)
    private String conditions;

    @Column(length = 500)
    private String requiredMaterials;

    private LocalDateTime applyStart;

    private LocalDateTime applyEnd;

    private boolean published;

    private boolean publicized;

    private LocalDateTime publicityStart;

    private LocalDateTime publicityEnd;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
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

    public String getConditions() {
        return conditions;
    }

    public void setConditions(String conditions) {
        this.conditions = conditions;
    }

    public String getRequiredMaterials() {
        return requiredMaterials;
    }

    public void setRequiredMaterials(String requiredMaterials) {
        this.requiredMaterials = requiredMaterials;
    }

    public LocalDateTime getApplyStart() {
        return applyStart;
    }

    public void setApplyStart(LocalDateTime applyStart) {
        this.applyStart = applyStart;
    }

    public LocalDateTime getApplyEnd() {
        return applyEnd;
    }

    public void setApplyEnd(LocalDateTime applyEnd) {
        this.applyEnd = applyEnd;
    }

    public boolean isPublished() {
        return published;
    }

    public void setPublished(boolean published) {
        this.published = published;
    }

    public boolean isPublicized() {
        return publicized;
    }

    public void setPublicized(boolean publicized) {
        this.publicized = publicized;
    }

    public LocalDateTime getPublicityStart() {
        return publicityStart;
    }

    public void setPublicityStart(LocalDateTime publicityStart) {
        this.publicityStart = publicityStart;
    }

    public LocalDateTime getPublicityEnd() {
        return publicityEnd;
    }

    public void setPublicityEnd(LocalDateTime publicityEnd) {
        this.publicityEnd = publicityEnd;
    }
}
