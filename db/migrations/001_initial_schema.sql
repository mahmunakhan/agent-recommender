-- ============================================================================
-- AI JOB RECOMMENDATION ENGINE - DATABASE SCHEMA
-- MySQL 8.0 Compatible
-- ============================================================================

-- Use the database
USE job_recommendation;

-- ============================================================================
-- 1. USERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('candidate', 'recruiter', 'admin') NOT NULL DEFAULT 'candidate',
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_users_email (email),
    INDEX idx_users_role (role),
    INDEX idx_users_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 2. PROFILES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS profiles (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id CHAR(36) NOT NULL UNIQUE,
    resume_s3_path VARCHAR(500),
    resume_text_extracted LONGTEXT,
    parsed_json_draft JSON,
    validated_json JSON,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verification_score FLOAT CHECK (verification_score >= 0 AND verification_score <= 1),
    headline VARCHAR(255),
    summary TEXT,
    location_city VARCHAR(100),
    location_country VARCHAR(100),
    years_experience INT CHECK (years_experience >= 0),
    desired_role VARCHAR(255),
    desired_salary_min INT,
    desired_salary_max INT,
    salary_currency VARCHAR(3) DEFAULT 'USD',
    is_open_to_work BOOLEAN NOT NULL DEFAULT TRUE,
    last_vectorized_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_profiles_is_verified (is_verified),
    INDEX idx_profiles_is_open_to_work (is_open_to_work),
    INDEX idx_profiles_location (location_country, location_city)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 3. SKILL CATEGORIES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS skill_categories (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    parent_id CHAR(36),
    description TEXT,
    icon VARCHAR(50),
    display_order INT NOT NULL DEFAULT 0,
    level INT NOT NULL DEFAULT 0,
    path VARCHAR(500) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (parent_id) REFERENCES skill_categories(id) ON DELETE SET NULL,
    INDEX idx_skill_categories_parent (parent_id),
    INDEX idx_skill_categories_path (path),
    INDEX idx_skill_categories_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 4. SKILLS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS skills (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    category_id CHAR(36) NOT NULL,
    description TEXT,
    skill_type ENUM('technical', 'soft', 'domain', 'tool', 'language', 'certification') NOT NULL,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    popularity_score FLOAT NOT NULL DEFAULT 0,
    trending_score FLOAT NOT NULL DEFAULT 0,
    external_ids JSON,
    metadata JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (category_id) REFERENCES skill_categories(id),
    INDEX idx_skills_category (category_id),
    INDEX idx_skills_type (skill_type),
    INDEX idx_skills_popularity (popularity_score DESC),
    FULLTEXT INDEX idx_skills_name_search (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 5. SKILL ALIASES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS skill_aliases (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    skill_id CHAR(36) NOT NULL,
    alias VARCHAR(100) NOT NULL,
    alias_type ENUM('abbreviation', 'alternate', 'misspelling', 'regional', 'version') NOT NULL,
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    is_preferred BOOLEAN NOT NULL DEFAULT FALSE,
    source VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    UNIQUE INDEX idx_skill_aliases_alias (alias),
    INDEX idx_skill_aliases_skill (skill_id),
    FULLTEXT INDEX idx_skill_aliases_search (alias)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 6. PROFILE SKILLS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS profile_skills (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    profile_id CHAR(36) NOT NULL,
    skill_id CHAR(36) NOT NULL,
    proficiency_level ENUM('beginner', 'intermediate', 'advanced', 'expert') NOT NULL,
    years_experience FLOAT CHECK (years_experience >= 0),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    source ENUM('parsed', 'manual', 'inferred') NOT NULL,
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    last_used_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    UNIQUE INDEX idx_profile_skills_unique (profile_id, skill_id),
    INDEX idx_profile_skills_proficiency (proficiency_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 7. JOB SOURCES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS job_sources (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    name VARCHAR(100) NOT NULL UNIQUE,
    source_type ENUM('scraper', 'api', 'manual', 'rss') NOT NULL,
    base_url VARCHAR(500),
    config_json JSON,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_sync_at TIMESTAMP NULL,
    sync_frequency_hours INT NOT NULL DEFAULT 24,
    jobs_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 8. JOBS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS jobs (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    source_id CHAR(36),
    external_id VARCHAR(255),
    source_type ENUM('internal', 'scrape', 'upload', 'api') NOT NULL,
    title VARCHAR(255) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    company_logo_url VARCHAR(500),
    description_raw LONGTEXT NOT NULL,
    description_clean LONGTEXT,
    requirements_json JSON,
    location_city VARCHAR(100),
    location_country VARCHAR(100),
    location_type ENUM('onsite', 'remote', 'hybrid') NOT NULL DEFAULT 'onsite',
    employment_type ENUM('full_time', 'part_time', 'contract', 'internship') NOT NULL DEFAULT 'full_time',
    salary_min INT,
    salary_max INT,
    salary_currency VARCHAR(3) DEFAULT 'USD',
    experience_min_years INT CHECK (experience_min_years >= 0),
    experience_max_years INT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    posted_at TIMESTAMP NULL,
    expires_at TIMESTAMP NULL,
    last_vectorized_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (source_id) REFERENCES job_sources(id) ON DELETE SET NULL,
    UNIQUE INDEX idx_jobs_source_external (source_id, external_id),
    INDEX idx_jobs_is_active (is_active),
    INDEX idx_jobs_location (location_country, location_city),
    INDEX idx_jobs_location_type (location_type),
    INDEX idx_jobs_posted_at (posted_at DESC),
    FULLTEXT INDEX idx_jobs_title_search (title)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 9. JOB SKILLS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS job_skills (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    job_id CHAR(36) NOT NULL,
    skill_id CHAR(36) NOT NULL,
    requirement_type ENUM('required', 'preferred', 'nice_to_have') NOT NULL,
    min_years INT CHECK (min_years >= 0),
    min_proficiency ENUM('beginner', 'intermediate', 'advanced', 'expert'),
    weight FLOAT NOT NULL DEFAULT 1.0 CHECK (weight >= 0 AND weight <= 10),
    extracted_text VARCHAR(255),
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    UNIQUE INDEX idx_job_skills_unique (job_id, skill_id),
    INDEX idx_job_skills_requirement (requirement_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 10. RECOMMENDATIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS recommendations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    job_id CHAR(36) NOT NULL,
    batch_id CHAR(36) NOT NULL,
    match_score FLOAT NOT NULL CHECK (match_score >= 0 AND match_score <= 100),
    skill_match_score FLOAT NOT NULL CHECK (skill_match_score >= 0 AND skill_match_score <= 100),
    experience_match_score FLOAT NOT NULL CHECK (experience_match_score >= 0 AND experience_match_score <= 100),
    location_match_score FLOAT NOT NULL CHECK (location_match_score >= 0 AND location_match_score <= 100),
    semantic_similarity FLOAT NOT NULL CHECK (semantic_similarity >= 0 AND semantic_similarity <= 1),
    ranking_position INT NOT NULL,
    matched_skills JSON NOT NULL,
    missing_skills JSON NOT NULL,
    gap_analysis TEXT,
    recommendation_reason TEXT,
    user_feedback ENUM('interested', 'not_interested', 'applied', 'saved'),
    feedback_at TIMESTAMP NULL,
    is_viewed BOOLEAN NOT NULL DEFAULT FALSE,
    viewed_at TIMESTAMP NULL,
    expires_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    UNIQUE INDEX idx_recommendations_user_job (user_id, job_id),
    INDEX idx_recommendations_user_score (user_id, match_score DESC),
    INDEX idx_recommendations_batch (batch_id),
    INDEX idx_recommendations_created (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 11. SKILL GAPS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS skill_gaps (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id CHAR(36) NOT NULL,
    skill_id CHAR(36) NOT NULL,
    gap_type ENUM('missing', 'insufficient', 'outdated') NOT NULL,
    current_level ENUM('none', 'beginner', 'intermediate', 'advanced', 'expert'),
    target_level ENUM('beginner', 'intermediate', 'advanced', 'expert') NOT NULL,
    priority_score FLOAT NOT NULL CHECK (priority_score >= 0 AND priority_score <= 100),
    frequency_in_jobs INT NOT NULL DEFAULT 0,
    avg_salary_impact FLOAT,
    source ENUM('job_matching', 'market_analysis', 'manual') NOT NULL,
    analysis_text TEXT,
    is_addressed BOOLEAN NOT NULL DEFAULT FALSE,
    addressed_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    UNIQUE INDEX idx_skill_gaps_user_skill (user_id, skill_id),
    INDEX idx_skill_gaps_priority (user_id, priority_score DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 12. LEARNING PROVIDERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS learning_providers (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    website_url VARCHAR(500) NOT NULL,
    logo_url VARCHAR(500),
    provider_type ENUM('mooc', 'video', 'documentation', 'certification', 'bootcamp') NOT NULL,
    quality_score FLOAT NOT NULL DEFAULT 50 CHECK (quality_score >= 0 AND quality_score <= 100),
    has_certificates BOOLEAN NOT NULL DEFAULT FALSE,
    has_free_content BOOLEAN NOT NULL DEFAULT FALSE,
    avg_course_price FLOAT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 13. LEARNING RESOURCES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS learning_resources (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    provider_id CHAR(36) NOT NULL,
    skill_id CHAR(36) NOT NULL,
    title VARCHAR(255) NOT NULL,
    url VARCHAR(500) NOT NULL,
    description TEXT,
    resource_type ENUM('course', 'tutorial', 'video', 'book', 'certification', 'article') NOT NULL,
    difficulty_level ENUM('beginner', 'intermediate', 'advanced', 'expert') NOT NULL,
    duration_hours FLOAT CHECK (duration_hours >= 0),
    price FLOAT CHECK (price >= 0),
    is_free BOOLEAN NOT NULL DEFAULT FALSE,
    rating FLOAT CHECK (rating >= 0 AND rating <= 5),
    reviews_count INT CHECK (reviews_count >= 0),
    enrollment_count INT CHECK (enrollment_count >= 0),
    has_certificate BOOLEAN NOT NULL DEFAULT FALSE,
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    quality_score FLOAT NOT NULL DEFAULT 50 CHECK (quality_score >= 0 AND quality_score <= 100),
    last_verified_at TIMESTAMP NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (provider_id) REFERENCES learning_providers(id),
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    INDEX idx_learning_resources_skill (skill_id),
    INDEX idx_learning_resources_provider (provider_id),
    INDEX idx_learning_resources_difficulty (difficulty_level),
    INDEX idx_learning_resources_quality (quality_score DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 14. USER LEARNING PATHS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_learning_paths (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id CHAR(36) NOT NULL,
    skill_gap_id CHAR(36),
    resource_id CHAR(36) NOT NULL,
    sequence_order INT NOT NULL,
    priority ENUM('critical', 'high', 'medium', 'low') NOT NULL,
    status ENUM('recommended', 'in_progress', 'completed', 'skipped') NOT NULL DEFAULT 'recommended',
    recommended_reason TEXT,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    user_rating INT CHECK (user_rating >= 1 AND user_rating <= 5),
    user_notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_gap_id) REFERENCES skill_gaps(id) ON DELETE SET NULL,
    FOREIGN KEY (resource_id) REFERENCES learning_resources(id) ON DELETE CASCADE,
    INDEX idx_user_learning_paths_user_order (user_id, sequence_order),
    INDEX idx_user_learning_paths_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 15. APPLICATIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS applications (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id CHAR(36) NOT NULL,
    job_id CHAR(36) NOT NULL,
    recommendation_id BIGINT,
    status ENUM('applied', 'screening', 'shortlisted', 'interview_scheduled', 'interviewed', 'offer_extended', 'offer_accepted', 'offer_declined', 'rejected', 'withdrawn') NOT NULL DEFAULT 'applied',
    cover_letter TEXT,
    custom_resume_path VARCHAR(500),
    source ENUM('recommendation', 'search', 'direct', 'referral') NOT NULL,
    match_score_at_apply FLOAT,
    recruiter_notes TEXT,
    rejection_reason VARCHAR(100),
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (recommendation_id) REFERENCES recommendations(id) ON DELETE SET NULL,
    UNIQUE INDEX idx_applications_user_job (user_id, job_id),
    INDEX idx_applications_status (status),
    INDEX idx_applications_applied_at (applied_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 16. RECRUITER ACTIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS recruiter_actions (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    application_id CHAR(36) NOT NULL,
    recruiter_id CHAR(36) NOT NULL,
    action_type ENUM('viewed', 'shortlisted', 'rejected', 'scheduled_interview', 'sent_message', 'status_changed', 'note_added') NOT NULL,
    previous_status VARCHAR(30),
    new_status VARCHAR(30),
    action_details JSON,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE,
    FOREIGN KEY (recruiter_id) REFERENCES users(id),
    INDEX idx_recruiter_actions_application (application_id),
    INDEX idx_recruiter_actions_recruiter (recruiter_id),
    INDEX idx_recruiter_actions_created (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 17. MARKET INTELLIGENCE TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS market_intelligence (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role_category VARCHAR(100) NOT NULL,
    location_scope VARCHAR(100) NOT NULL DEFAULT 'global',
    analysis_type ENUM('skill_demand', 'salary_trend', 'job_volume', 'emerging_roles') NOT NULL,
    data_json JSON NOT NULL,
    summary_text TEXT,
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    sources JSON,
    agent_id VARCHAR(100) NOT NULL,
    fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP NOT NULL,
    
    INDEX idx_market_intelligence_role (role_category),
    INDEX idx_market_intelligence_type (analysis_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 18. TRENDING SKILLS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS trending_skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    skill_id CHAR(36) NOT NULL,
    period_start DATE NOT NULL,
    period_type ENUM('daily', 'weekly', 'monthly') NOT NULL,
    job_posting_count INT NOT NULL DEFAULT 0,
    avg_salary FLOAT,
    demand_score FLOAT NOT NULL DEFAULT 0,
    growth_rate FLOAT,
    location_scope VARCHAR(100) NOT NULL DEFAULT 'global',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    UNIQUE INDEX idx_trending_skills_unique (skill_id, period_start, period_type, location_scope),
    INDEX idx_trending_skills_period (period_start DESC),
    INDEX idx_trending_skills_demand (demand_score DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 19. AUDIT LOG TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    event_category ENUM('user', 'job', 'recommendation', 'system', 'security', 'ai') NOT NULL,
    actor_id CHAR(36),
    actor_type ENUM('user', 'system', 'agent', 'api') NOT NULL,
    target_type VARCHAR(50),
    target_id VARCHAR(100),
    action ENUM('create', 'read', 'update', 'delete', 'login', 'logout', 'error') NOT NULL,
    old_values JSON,
    new_values JSON,
    metadata JSON,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_audit_log_created (created_at DESC),
    INDEX idx_audit_log_actor (actor_id),
    INDEX idx_audit_log_target (target_type, target_id),
    INDEX idx_audit_log_event (event_type),
    INDEX idx_audit_log_category (event_category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 20. NOTIFICATIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS notifications (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id CHAR(36) NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    action_url VARCHAR(500),
    metadata JSON,
    priority ENUM('low', 'normal', 'high', 'urgent') NOT NULL DEFAULT 'normal',
    channels JSON NOT NULL DEFAULT ('["in_app"]'),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    read_at TIMESTAMP NULL,
    is_sent BOOLEAN NOT NULL DEFAULT FALSE,
    sent_at TIMESTAMP NULL,
    expires_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_notifications_user_unread (user_id, is_read),
    INDEX idx_notifications_user_created (user_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================
SELECT 'All 20 tables created successfully!' AS status;