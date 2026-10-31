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
-- Table structure for table `desglose_efectivo`
--

DROP TABLE IF EXISTS `desglose_efectivo`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `desglose_efectivo` (
  `id` int NOT NULL AUTO_INCREMENT,
  `pago_id` int NOT NULL,
  `denominacion` int NOT NULL,
  `cantidad` int NOT NULL DEFAULT '0',
  `tipo` enum('billete','moneda') NOT NULL,
  PRIMARY KEY (`id`),
  KEY `pago_id` (`pago_id`),
  CONSTRAINT `desglose_efectivo_ibfk_1` FOREIGN KEY (`pago_id`) REFERENCES `pagos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=40 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `desglose_efectivo`
--

LOCK TABLES `desglose_efectivo` WRITE;
/*!40000 ALTER TABLE `desglose_efectivo` DISABLE KEYS */;
INSERT INTO `desglose_efectivo` VALUES (1,16,100000,1,'billete'),(2,17,50000,6,'billete'),(3,18,100000,1,'billete'),(4,18,50000,1,'billete'),(5,18,20000,2,'billete'),(6,19,50000,1,'billete'),(7,19,10000,1,'billete'),(8,20,50000,1,'billete'),(9,20,20000,1,'billete'),(10,21,20000,1,'billete'),(11,21,10000,1,'billete'),(12,22,10000,1,'billete'),(13,22,2000,1,'billete'),(14,23,100000,1,'billete'),(15,23,50000,1,'billete'),(16,23,10000,1,'billete'),(17,23,5000,1,'billete'),(18,23,2000,1,'billete'),(19,24,2000,1,'billete'),(20,24,1000,1,'billete'),(21,24,500,1,'moneda'),(22,24,200,1,'moneda'),(23,24,100,2,'moneda'),(24,24,50,2,'moneda'),(25,25,100,1,'moneda'),(26,25,50,2,'moneda'),(27,26,500,1,'moneda'),(28,26,200,1,'moneda'),(29,26,100,1,'moneda'),(30,26,50,1,'moneda'),(33,29,100000,1,'billete'),(34,29,20000,1,'billete'),(35,30,100000,1,'billete'),(36,30,50000,2,'billete'),(37,30,20000,2,'billete'),(38,30,10000,2,'billete'),(39,30,5000,2,'billete');
/*!40000 ALTER TABLE `desglose_efectivo` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-05-19 21:26:46
