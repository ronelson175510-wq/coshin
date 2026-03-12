-- Migration script to update notifications table
-- Run this if your database already exists and you need to add new columns

USE coshin;

-- Add new columns to notifications table
ALTER TABLE notifications 
ADD COLUMN IF NOT EXISTS from_user_id INT AFTER user_id,
ADD COLUMN IF NOT EXISTS content_type VARCHAR(50) AFTER message,
ADD COLUMN IF NOT EXISTS content_id INT AFTER content_type,
ADD COLUMN IF NOT EXISTS action_data TEXT AFTER content_id;

-- Add foreign key constraint
ALTER TABLE notifications
ADD CONSTRAINT fk_notifications_from_user
FOREIGN KEY (from_user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_from_user_id ON notifications(from_user_id);
CREATE INDEX IF NOT EXISTS idx_is_read ON notifications(is_read);

SELECT 'Notifications table migration completed successfully!' AS message;
