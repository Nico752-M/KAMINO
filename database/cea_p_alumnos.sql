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
-- Table structure for table `alumnos`
--

DROP TABLE IF EXISTS `alumnos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alumnos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `numero_documento` varchar(20) NOT NULL,
  `tipo_documento` enum('CC','CE','TI','PAS') NOT NULL DEFAULT 'CC',
  `nombres` varchar(100) NOT NULL,
  `apellidos` varchar(100) NOT NULL,
  `fecha_nacimiento` date DEFAULT NULL,
  `lugar_nacimiento` varchar(100) DEFAULT NULL,
  `sexo` enum('M','F') DEFAULT NULL,
  `estado_civil` enum('Soltero','Casado','Divorciado','Viudo','Union Libre') DEFAULT NULL,
  `estatura` decimal(4,2) DEFAULT NULL,
  `grupo_sanguineo` enum('O+','O-','A+','A-','B+','B-','AB+','AB-') DEFAULT NULL,
  `celular` varchar(20) DEFAULT NULL,
  `email` varchar(150) DEFAULT NULL,
  `ocupacion` varchar(100) DEFAULT NULL,
  `foto_path` varchar(500) DEFAULT NULL,
  `categoria` varchar(20) NOT NULL,
  `estado` enum('Activo','Completado','Pendiente Pago','Cancelado') NOT NULL DEFAULT 'Activo',
  `observaciones` text,
  `fecha_registro` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `precio_total` int DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `numero_documento` (`numero_documento`),
  KEY `idx_documento` (`numero_documento`),
  KEY `idx_nombres` (`nombres`,`apellidos`),
  KEY `idx_estado` (`estado`),
  KEY `idx_categoria` (`categoria`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `alumnos`
--

LOCK TABLES `alumnos` WRITE;
/*!40000 ALTER TABLE `alumnos` DISABLE KEYS */;
INSERT INTO `alumnos` VALUES (8,'3','CC','Q','Q','2001-05-17','E','M','Soltero',1.22,'O+','3123','D','W',NULL,'A1','Activo',NULL,'2026-05-17 18:10:17',0),(9,'1','CC','N','M','2001-05-17','Q','M','Soltero',1.77,'O+','33','QQQ','E',NULL,'A1','Activo',NULL,'2026-05-17 18:25:36',0),(11,'4','CC','A','L','2001-05-18','CALI','M','Soltero',1.77,'O+','3122141','DDSA DA','ESCLAVO',NULL,'A1','Activo',NULL,'2026-05-18 09:06:13',0),(12,'5','CC','P','L','2001-05-18','CALK','F','Soltero',1.56,'O+','231','DAS AGG','NOSE',NULL,'A1','Activo',NULL,'2026-05-18 09:13:35',0),(13,'6','CC','Paulina','Llano','2001-05-18','tulua','M','Soltero',1.60,'O+','3177554350','nicotin5579@gmail.com','Estudiante',NULL,'A1','Activo',NULL,'2026-05-18 13:45:01',0),(14,'3333','CC','QW','WW','2001-05-18','WW','M','Soltero',1.77,'O-','22','DEEE','WW',NULL,'A1','Activo',NULL,'2026-05-18 13:51:02',0);
/*!40000 ALTER TABLE `alumnos` ENABLE KEYS */;
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
