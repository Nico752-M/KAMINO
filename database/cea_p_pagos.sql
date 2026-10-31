-- MySQL dump 10.13  Distrib 8.0.45, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: cea_p
-- ------------------------------------------------------
-- Server version	8.0.45

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `pagos`
--

DROP TABLE IF EXISTS `pagos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pagos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `alumno_id` int NOT NULL,
  `concepto` varchar(200) NOT NULL,
  `valor` decimal(12,2) NOT NULL,
  `metodo_pago` enum('Efectivo','Transferencia','Nequi','Daviplata','Otro') NOT NULL DEFAULT 'Efectivo',
  `numero_recibo` varchar(50) NOT NULL,
  `fecha_pago` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `usuario_id` int NOT NULL,
  `observaciones` text,
  PRIMARY KEY (`id`),
  UNIQUE KEY `numero_recibo` (`numero_recibo`),
  KEY `fk_pagos_usuario` (`usuario_id`),
  KEY `idx_alumno_id` (`alumno_id`),
  KEY `idx_fecha_pago` (`fecha_pago`),
  KEY `idx_recibo` (`numero_recibo`),
  CONSTRAINT `fk_pagos_alumno` FOREIGN KEY (`alumno_id`) REFERENCES `alumnos` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_pagos_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=31 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pagos`
--

LOCK TABLES `pagos` WRITE;
/*!40000 ALTER TABLE `pagos` DISABLE KEYS */;
INSERT INTO `pagos` VALUES (8,8,'Pago curso de conducción',1000.00,'Efectivo','CEA-20260517-54CE','2026-05-17 18:11:14',1,''),(9,8,'Pago curso de conducción',100000.00,'Efectivo','CEA-20260517-5633','2026-05-17 18:11:50',1,''),(10,9,'Pago curso de conducción',200000.00,'Efectivo','CEA-20260517-1767','2026-05-17 18:26:00',1,''),(11,9,'Pago curso de conducción',250000.00,'Efectivo','CEA-20260517-A776','2026-05-17 18:31:43',1,''),(12,9,'Pago curso de conducción',100000.00,'Efectivo','CEA-20260517-2388','2026-05-17 18:33:58',1,''),(13,9,'Pago curso de conducción',200000.00,'Efectivo','CEA-20260517-718D','2026-05-17 18:34:29',1,''),(16,11,'Pago curso de conducción',100000.00,'Efectivo','CEA-20260518-E37E','2026-05-18 09:06:30',1,''),(17,11,'Pago curso de conducción',300000.00,'Efectivo','CEA-20260518-A59E','2026-05-18 09:06:39',1,''),(18,12,'Pago curso de conducción',190000.00,'Efectivo','CEA-20260518-0B73','2026-05-18 09:14:01',1,''),(19,12,'Pago curso de conducción',60000.00,'Efectivo','CEA-20260518-3B8F','2026-05-18 09:24:30',1,''),(20,12,'Pago curso de conducción',70000.00,'Efectivo','CEA-20260518-1585','2026-05-18 09:34:21',1,''),(21,12,'Pago curso de conducción',30000.00,'Efectivo','CEA-20260518-89E2','2026-05-18 13:42:32',1,''),(22,13,'Pago curso de conducción',12000.00,'Efectivo','CEA-20260518-2A66','2026-05-18 13:45:42',1,''),(23,13,'Pago curso de conducción',167000.00,'Efectivo','CEA-20260518-C503','2026-05-18 13:47:02',1,''),(24,13,'Pago curso de conducción',4000.00,'Efectivo','CEA-20260518-768C','2026-05-18 13:47:33',1,''),(25,14,'Pago curso de conducción',200.00,'Efectivo','CEA-20260518-BCF1','2026-05-18 13:51:48',1,''),(26,14,'Pago curso de conducción',850.00,'Efectivo','CEA-20260518-43A1','2026-05-18 13:52:20',1,''),(29,13,'Pago curso de conducción',120000.00,'Efectivo','CEA-20260518-A0DE','2026-05-18 21:50:12',1,''),(30,12,'Pago curso de conducción',270000.00,'Efectivo','CEA-20260519-6521','2026-05-19 19:18:20',1,'');
/*!40000 ALTER TABLE `pagos` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-05-19 21:26:47
