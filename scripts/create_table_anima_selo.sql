-- Migration para criação das tabelas de selos e relacionamento com usuário
-- Tabela: anima_selo (hierárquica)
-- Tabela: anima_usuario_selo (vínculo selo <-> usuario)

CREATE TABLE IF NOT EXISTS `anima_selo` (
  `selo_id` INT NOT NULL AUTO_INCREMENT,
  `selo_nome` VARCHAR(100) NOT NULL,
  `selo_parceiro` CHAR(20) NOT NULL,
  `selo_parent_id` INT NULL,
  PRIMARY KEY (`selo_id`),
  INDEX `fk_anima_selo_parent_idx` (`selo_parent_id` ASC),
  CONSTRAINT `fk_anima_selo_parent`
    FOREIGN KEY (`selo_parent_id`)
    REFERENCES `anima_selo` (`selo_id`)
    ON DELETE RESTRICT
    ON UPDATE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE IF NOT EXISTS `anima_usuario_selo` (
  `usuario_id` INT NOT NULL,
  `selo_id` INT NOT NULL,
  `usuario_selo_data` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`usuario_id`, `selo_id`),
  INDEX `fk_anima_usuario_selo_selo_idx` (`selo_id` ASC),
  INDEX `fk_anima_usuario_selo_usuario_idx` (`usuario_id` ASC),
  CONSTRAINT `fk_anima_usuario_selo_usuario`
    FOREIGN KEY (`usuario_id`)
    REFERENCES `usuario` (`usuario_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_anima_usuario_selo_selo`
    FOREIGN KEY (`selo_id`)
    REFERENCES `anima_selo` (`selo_id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
