-- =====================================================
-- Migration: Decouple Questions from Quizzes (Question Bank)
-- =====================================================

-- 1. Tabela associativa entre Pergunta e Temas de Interesse
CREATE TABLE IF NOT EXISTS `anima_pergunta_tema` (
  `pergunta_id` INT NOT NULL,
  `temas_interesse_id` INT NOT NULL,
  PRIMARY KEY (`pergunta_id`, `temas_interesse_id`),
  INDEX `fk_anima_pergunta_tema_pergunta_idx` (`pergunta_id` ASC),
  INDEX `fk_anima_pergunta_tema_tema_idx` (`temas_interesse_id` ASC),
  CONSTRAINT `fk_anima_pergunta_tema_pergunta`
    FOREIGN KEY (`pergunta_id`)
    REFERENCES `anima_quiz_pergunta` (`pergunta_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_anima_pergunta_tema_tema`
    FOREIGN KEY (`temas_interesse_id`)
    REFERENCES `anima_temas_interesse` (`temas_interesse_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 2. Tabela associativa entre Quiz e Perguntas (permite reuso de perguntas em múltiplos quizes)
CREATE TABLE IF NOT EXISTS `anima_quiz_pergunta_assoc` (
  `quiz_id` INT NOT NULL,
  `pergunta_id` INT NOT NULL,
  `ordem` INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`quiz_id`, `pergunta_id`),
  INDEX `fk_anima_quiz_pergunta_assoc_quiz_idx` (`quiz_id` ASC),
  INDEX `fk_anima_quiz_pergunta_assoc_pergunta_idx` (`pergunta_id` ASC),
  CONSTRAINT `fk_anima_quiz_pergunta_assoc_quiz`
    FOREIGN KEY (`quiz_id`)
    REFERENCES `anima_quiz` (`quiz_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_anima_quiz_pergunta_assoc_pergunta`
    FOREIGN KEY (`pergunta_id`)
    REFERENCES `anima_quiz_pergunta` (`pergunta_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 3. Migrar perguntas já existentes na tabela associativa caso anima_quiz_pergunta ainda tenha quiz_id
INSERT IGNORE INTO `anima_quiz_pergunta_assoc` (quiz_id, pergunta_id, ordem)
SELECT quiz_id, pergunta_id, COALESCE(pergunta_ordem, 1)
FROM `anima_quiz_pergunta`
WHERE quiz_id IS NOT NULL;

-- 4. Tornar quiz_id nullable na tabela anima_quiz_pergunta (para perguntas do banco independente)
ALTER TABLE `anima_quiz_pergunta` MODIFY COLUMN `quiz_id` INT NULL;
