USE `algo_trading`;

CREATE TABLE `quotes` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `ticker` varchar(10) DEFAULT NULL,
  `price` decimal(10,4) DEFAULT NULL,
  `ask` decimal(10,4) DEFAULT NULL,
  `bid` decimal(10,4) DEFAULT NULL,
  `volume` bigint(20) DEFAULT NULL,
  `delayed` bit(1) DEFAULT NULL,
  `time_correction_sec` int(11) DEFAULT NULL,
  `initial` bit(1) DEFAULT NULL,
  `datetime_newyork` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_ticker_dt` (`ticker`,`datetime_newyork`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=latin1;
