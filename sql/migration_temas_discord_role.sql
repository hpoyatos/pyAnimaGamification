-- =====================================================
-- Migration: Adiciona discord_role_id na tabela de Temas de Interesse
-- =====================================================

ALTER TABLE `anima_temas_interesse` 
ADD COLUMN IF NOT EXISTS `discord_role_id` VARCHAR(20) NULL AFTER `temas_interesse_descricao`;

-- Exemplo: Atualiza tema de Inteligência Artificial para vincular à Role solicitada (1212540672482222151)
UPDATE `anima_temas_interesse`
SET `discord_role_id` = '1212540672482222151'
WHERE `temas_interesse_nome` LIKE '%Inteligência Artificial%' 
   OR `temas_interesse_nome` LIKE '%IA%' 
   OR `temas_interesse_tag` = 'IA';
