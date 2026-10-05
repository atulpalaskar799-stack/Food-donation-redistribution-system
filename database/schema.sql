CREATE DATABASE IF NOT EXISTS food_redistribution_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE food_redistribution_db;

CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(190) NOT NULL UNIQUE,
    phone VARCHAR(30),
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('donor','ngo','volunteer','admin') NOT NULL,
    status ENUM('active','inactive','blocked') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_role(role), INDEX idx_users_status(status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS donor_profiles (
    donor_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    organization_name VARCHAR(150),
    address TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ngo_profiles (
    ngo_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    organization_name VARCHAR(150) NOT NULL,
    verification_status ENUM('pending','verified','rejected') NOT NULL DEFAULT 'pending',
    address TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_ngo_verification(verification_status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS volunteer_profiles (
    volunteer_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    availability ENUM('available','unavailable') NOT NULL DEFAULT 'available',
    area VARCHAR(150),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS food_categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS donations (
    donation_id INT AUTO_INCREMENT PRIMARY KEY,
    donor_id INT NOT NULL,
    category_id INT NOT NULL,
    food_name VARCHAR(180) NOT NULL,
    description TEXT,
    quantity DECIMAL(12,2) NOT NULL,
    unit VARCHAR(40) NOT NULL,
    prepared_at DATETIME NOT NULL,
    expiry_at DATETIME NOT NULL,
    pickup_availability VARCHAR(255) NOT NULL,
    pickup_address TEXT NOT NULL,
    notes TEXT,
    status ENUM('available','matched','accepted','volunteer_assigned','pickup_started','picked_up','out_for_delivery','delivered','confirmed','successfully_redistributed','cancelled','expired','rejected') NOT NULL DEFAULT 'available',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (donor_id) REFERENCES users(user_id),
    FOREIGN KEY (category_id) REFERENCES food_categories(category_id),
    INDEX idx_donations_status(status), INDEX idx_donations_expiry(expiry_at), INDEX idx_donations_category(category_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS requirements (
    requirement_id INT AUTO_INCREMENT PRIMARY KEY,
    ngo_id INT NOT NULL,
    category_id INT NOT NULL,
    quantity_required DECIMAL(12,2) NOT NULL,
    unit VARCHAR(40) NOT NULL,
    needed_by DATETIME NOT NULL,
    location VARCHAR(255) NOT NULL,
    description TEXT,
    status ENUM('open','matched','fulfilled','cancelled','expired') NOT NULL DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (ngo_id) REFERENCES users(user_id),
    FOREIGN KEY (category_id) REFERENCES food_categories(category_id),
    INDEX idx_requirements_status(status), INDEX idx_requirements_needed(needed_by)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS matches (
    match_id INT AUTO_INCREMENT PRIMARY KEY,
    donation_id INT NOT NULL,
    requirement_id INT NOT NULL,
    match_score DECIMAL(6,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_donation_requirement(donation_id, requirement_id),
    FOREIGN KEY (donation_id) REFERENCES donations(donation_id) ON DELETE CASCADE,
    FOREIGN KEY (requirement_id) REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    INDEX idx_match_score(match_score)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS assignments (
    assignment_id INT AUTO_INCREMENT PRIMARY KEY,
    donation_id INT NOT NULL,
    volunteer_id INT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pickup_status ENUM('assigned','pickup_started','picked_up') NOT NULL DEFAULT 'assigned',
    delivery_status ENUM('pending','out_for_delivery','delivered','confirmed') NOT NULL DEFAULT 'pending',
    FOREIGN KEY (donation_id) REFERENCES donations(donation_id) ON DELETE CASCADE,
    FOREIGN KEY (volunteer_id) REFERENCES users(user_id),
    UNIQUE KEY uq_donation_assignment(donation_id),
    INDEX idx_assignment_volunteer(volunteer_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS donation_history (
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    donation_id INT NOT NULL,
    status VARCHAR(60) NOT NULL,
    changed_by INT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    remarks VARCHAR(500),
    FOREIGN KEY (donation_id) REFERENCES donations(donation_id) ON DELETE CASCADE,
    FOREIGN KEY (changed_by) REFERENCES users(user_id) ON DELETE SET NULL,
    INDEX idx_history_donation(donation_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS point_transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    activity_type VARCHAR(100) NOT NULL,
    points INT NOT NULL,
    reference_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE KEY uq_activity_reference(user_id, activity_type, reference_id),
    INDEX idx_points_user(user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS rankings (
    ranking_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    category ENUM('donor','ngo','volunteer','overall') NOT NULL,
    period ENUM('monthly','quarterly','all_time') NOT NULL DEFAULT 'all_time',
    points INT NOT NULL DEFAULT 0,
    rank_position INT NOT NULL,
    successful_activities INT NOT NULL DEFAULT 0,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_rank_category(category, period, rank_position)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS notifications (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(180) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_notifications_user(user_id, is_read)
) ENGINE=InnoDB;

INSERT IGNORE INTO food_categories(name, description) VALUES
('Cooked Meals','Prepared meals and lunch/dinner food'),
('Bakery','Bread, buns, cakes and bakery products'),
('Fruits','Fresh fruits'),
('Vegetables','Fresh vegetables'),
('Groceries','Packaged groceries and staples'),
('Beverages','Milk, juice and non-alcoholic beverages');
