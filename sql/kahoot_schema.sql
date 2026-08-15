-- =====================================================
-- Migration: Kahoot Gamification Schema for MariaDB
-- =====================================================

-- 1. Tabela de Usuário Discord (Desacoplada)
CREATE TABLE IF NOT EXISTS `anima_usuario_discord` (
  `discord_user_id` VARCHAR(25) NOT NULL,
  `discord_username` VARCHAR(100) NULL,
  `discord_global_name` VARCHAR(100) NULL,
  `discord_avatar_url` VARCHAR(255) NULL,
  `usuario_id` INT NULL,
  `data_criacao` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `data_atualizacao` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`discord_user_id`),
  INDEX `fk_anima_usuario_discord_usuario_idx` (`usuario_id` ASC),
  CONSTRAINT `fk_anima_usuario_discord_usuario`
    FOREIGN KEY (`usuario_id`)
    REFERENCES `usuario` (`usuario_id`)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 2. Tabela de Quiz (Master)
CREATE TABLE IF NOT EXISTS `anima_quiz` (
  `quiz_id` INT NOT NULL AUTO_INCREMENT,
  `quiz_titulo` VARCHAR(150) NOT NULL,
  `quiz_descricao` TEXT NULL,
  `data_criacao` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `data_atualizacao` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`quiz_id`)
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 3. Tabela Associativa Quiz <-> Temas de Interesse
CREATE TABLE IF NOT EXISTS `anima_quiz_tema` (
  `quiz_id` INT NOT NULL,
  `temas_interesse_id` INT NOT NULL,
  PRIMARY KEY (`quiz_id`, `temas_interesse_id`),
  INDEX `fk_anima_quiz_tema_tema_idx` (`temas_interesse_id` ASC),
  CONSTRAINT `fk_anima_quiz_tema_quiz`
    FOREIGN KEY (`quiz_id`)
    REFERENCES `anima_quiz` (`quiz_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_anima_quiz_tema_tema`
    FOREIGN KEY (`temas_interesse_id`)
    REFERENCES `anima_temas_interesse` (`temas_interesse_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 4. Tabela de Perguntas do Quiz
CREATE TABLE IF NOT EXISTS `anima_quiz_pergunta` (
  `pergunta_id` INT NOT NULL AUTO_INCREMENT,
  `quiz_id` INT NOT NULL,
  `pergunta_ordem` INT NOT NULL DEFAULT 1,
  `pergunta_enunciado` TEXT NOT NULL,
  `pergunta_imagem_url` VARCHAR(500) NULL,
  `tempo_limite_segundos` INT NOT NULL DEFAULT 20,
  `pontos_base` INT NOT NULL DEFAULT 1000,
  `data_criacao` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`pergunta_id`),
  INDEX `fk_anima_quiz_pergunta_quiz_idx` (`quiz_id` ASC),
  CONSTRAINT `fk_anima_quiz_pergunta_quiz`
    FOREIGN KEY (`quiz_id`)
    REFERENCES `anima_quiz` (`quiz_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 5. Tabela de Alternativas (4 por pergunta, limite 100 chars, 1 correta)
CREATE TABLE IF NOT EXISTS `anima_quiz_alternativa` (
  `alternativa_id` INT NOT NULL AUTO_INCREMENT,
  `pergunta_id` INT NOT NULL,
  `alternativa_letra` CHAR(1) NOT NULL,
  `alternativa_texto` VARCHAR(100) NOT NULL,
  `is_correta` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`alternativa_id`),
  INDEX `fk_anima_quiz_alternativa_pergunta_idx` (`pergunta_id` ASC),
  CONSTRAINT `fk_anima_quiz_alternativa_pergunta`
    FOREIGN KEY (`pergunta_id`)
    REFERENCES `anima_quiz_pergunta` (`pergunta_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 6. Tabela de Agendamento / Aplicação do Quiz em UC
CREATE TABLE IF NOT EXISTS `anima_quiz_aplicacao` (
  `aplicacao_id` INT NOT NULL AUTO_INCREMENT,
  `quiz_id` INT NOT NULL,
  `uc_id` INT NOT NULL,
  `data_hora_prevista` DATETIME NOT NULL,
  `status` ENUM('Agendado', 'Em Andamento', 'Concluido', 'Cancelado') NOT NULL DEFAULT 'Agendado',
  `discord_channel_id` VARCHAR(25) NULL,
  `data_hora_inicio` DATETIME NULL,
  `data_hora_fim` DATETIME NULL,
  `pontos_1_lugar` DECIMAL(5,2) NOT NULL DEFAULT 1.00,
  `pontos_2_lugar` DECIMAL(5,2) NOT NULL DEFAULT 1.00,
  `pontos_3_lugar` DECIMAL(5,2) NOT NULL DEFAULT 1.00,
  `pontos_4_lugar` DECIMAL(5,2) NOT NULL DEFAULT 0.80,
  `pontos_5_lugar` DECIMAL(5,2) NOT NULL DEFAULT 0.80,
  `pontos_6_lugar` DECIMAL(5,2) NOT NULL DEFAULT 0.80,
  `pontos_7_lugar` DECIMAL(5,2) NOT NULL DEFAULT 0.50,
  `pontos_8_lugar` DECIMAL(5,2) NOT NULL DEFAULT 0.50,
  `pontos_9_lugar` DECIMAL(5,2) NOT NULL DEFAULT 0.50,
  `pontos_10_lugar` DECIMAL(5,2) NOT NULL DEFAULT 0.50,
  `data_criacao` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`aplicacao_id`),
  INDEX `fk_anima_quiz_aplicacao_quiz_idx` (`quiz_id` ASC),
  INDEX `fk_anima_quiz_aplicacao_uc_idx` (`uc_id` ASC),
  CONSTRAINT `fk_anima_quiz_aplicacao_quiz`
    FOREIGN KEY (`quiz_id`)
    REFERENCES `anima_quiz` (`quiz_id`)
    ON DELETE RESTRICT
    ON UPDATE CASCADE,
  CONSTRAINT `fk_anima_quiz_aplicacao_uc`
    FOREIGN KEY (`uc_id`)
    REFERENCES `anima_uc` (`uc_id`)
    ON DELETE RESTRICT
    ON UPDATE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 7. Tabela de Respostas em Tempo Real (Precisão de Milissegundos)
CREATE TABLE IF NOT EXISTS `anima_quiz_resposta` (
  `resposta_id` INT NOT NULL AUTO_INCREMENT,
  `aplicacao_id` INT NOT NULL,
  `pergunta_id` INT NOT NULL,
  `alternativa_id` INT NOT NULL,
  `discord_user_id` VARCHAR(25) NOT NULL,
  `data_hora_resposta` DATETIME(3) NOT NULL,
  `tempo_gasto_ms` INT NOT NULL,
  `is_correta` TINYINT(1) NOT NULL DEFAULT 0,
  `pontos_ganhos` INT NOT NULL DEFAULT 0,
  PRIMARY KEY (`resposta_id`),
  UNIQUE KEY `uk_aplicacao_pergunta_user` (`aplicacao_id`, `pergunta_id`, `discord_user_id`),
  INDEX `fk_anima_quiz_resposta_app_idx` (`aplicacao_id` ASC),
  INDEX `fk_anima_quiz_resposta_pergunta_idx` (`pergunta_id` ASC),
  INDEX `fk_anima_quiz_resposta_alt_idx` (`alternativa_id` ASC),
  INDEX `fk_anima_quiz_resposta_user_idx` (`discord_user_id` ASC),
  CONSTRAINT `fk_anima_quiz_resposta_app`
    FOREIGN KEY (`aplicacao_id`)
    REFERENCES `anima_quiz_aplicacao` (`aplicacao_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_anima_quiz_resposta_pergunta`
    FOREIGN KEY (`pergunta_id`)
    REFERENCES `anima_quiz_pergunta` (`pergunta_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_anima_quiz_resposta_alt`
    FOREIGN KEY (`alternativa_id`)
    REFERENCES `anima_quiz_alternativa` (`alternativa_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_anima_quiz_resposta_user`
    FOREIGN KEY (`discord_user_id`)
    REFERENCES `anima_usuario_discord` (`discord_user_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 8. Tabela de Ranking e Participantes do Quiz
CREATE TABLE IF NOT EXISTS `anima_quiz_participante` (
  `aplicacao_id` INT NOT NULL,
  `discord_user_id` VARCHAR(25) NOT NULL,
  `pontuacao_total` INT NOT NULL DEFAULT 0,
  `acertos` INT NOT NULL DEFAULT 0,
  `tempo_total_ms` INT NOT NULL DEFAULT 0,
  `posicao_final` INT NULL,
  `pontos_atribuidos` DECIMAL(5,2) NULL,
  PRIMARY KEY (`aplicacao_id`, `discord_user_id`),
  INDEX `fk_anima_quiz_part_user_idx` (`discord_user_id` ASC),
  CONSTRAINT `fk_anima_quiz_part_app`
    FOREIGN KEY (`aplicacao_id`)
    REFERENCES `anima_quiz_aplicacao` (`aplicacao_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_anima_quiz_part_user`
    FOREIGN KEY (`discord_user_id`)
    REFERENCES `anima_usuario_discord` (`discord_user_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
