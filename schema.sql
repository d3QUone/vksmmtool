DROP TABLE IF EXISTS `userinfo`;
CREATE TABLE `userinfo` (
  `user_id` INTEGER NOT NULL,
  `auth_token` TEXT,
  `sort_type` TEXT,
  `last_seen` TEXT,
  `username` TEXT,
  `picture` TEXT,
  `is_deleted` BOOL DEFAULT FALSE,
  PRIMARY KEY (`user_id`)
);

DROP TABLE IF EXISTS `groups`;
CREATE TABLE `groups` (
  `group_id` INTEGER NOT NULL,
  `user_id` INTEGER NOT NULL,
  `groupname` TEXT,
  `screen_name` TEXT,
  `picture` TEXT,
  `added` INTEGER,
  `is_old` INTEGER,
  `is_deleted` BOOL DEFAULT FALSE,
  PRIMARY KEY (`group_id`)
);

DROP TABLE IF EXISTS `postinfo`;
CREATE TABLE `postinfo` (
  `post_id` INTEGER NOT NULL,
  `group_id` INTEGER NOT NULL,
  `picture` TEXT,
  `content` TEXT,
  `link` TEXT,
  `like` INTEGER,
  `comm` INTEGER,
  `repo` INTEGER,
  `is_deleted` BOOL DEFAULT FALSE,
  PRIMARY KEY (`post_id`)
);

DROP TABLE IF EXISTS `screen_size`;
CREATE TABLE `screen_size` (
  `user_ip` TEXT NOT NULL,
  `w` INTEGER,
  `h` INTEGER,
  `is_banned` BOOL DEFAULT FALSE,
  PRIMARY KEY (`user_ip`)
);
