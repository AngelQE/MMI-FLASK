-- ============================================================
-- Esquema MySQL de mi_mundo_infantil (generado desde models.py)
-- Solo estructura. Los datos del reglamento y de prueba los carga:  python seed.py
-- ============================================================
DROP DATABASE IF EXISTS mi_mundo_infantil;
CREATE DATABASE mi_mundo_infantil CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE mi_mundo_infantil;

CREATE TABLE areas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(100) NOT NULL, 
	nivel ENUM('inicial','primaria') NOT NULL, 
	es_transversal BOOL NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE estudiantes (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(100) NOT NULL, 
	apellido VARCHAR(100) NOT NULL, 
	fecha_nacimiento DATE NOT NULL, 
	dni_documento VARCHAR(10), 
	tiene_nee BOOL NOT NULL, 
	salida_autonoma BOOL NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (dni_documento)
);

CREATE TABLE grados (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nivel ENUM('inicial','primaria') NOT NULL, 
	nombre VARCHAR(30) NOT NULL, 
	ciclo VARCHAR(5) NOT NULL, 
	edad_normativa INTEGER NOT NULL, 
	edad_maxima INTEGER NOT NULL, 
	hora_ingreso TIME NOT NULL, 
	hora_salida TIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE roles (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(100) NOT NULL, 
	descripcion TEXT, 
	PRIMARY KEY (id)
);

CREATE TABLE asistencias (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	estudiante_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	estado ENUM('presente','ausente','tardanza','justificado') NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_asistencia_dia UNIQUE (estudiante_id, fecha), 
	FOREIGN KEY(estudiante_id) REFERENCES estudiantes (id)
);

CREATE TABLE competencias (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	area_id INTEGER NOT NULL, 
	nombre VARCHAR(250) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(area_id) REFERENCES areas (id)
);

CREATE TABLE usuarios (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	role_id INTEGER, 
	nombre VARCHAR(100) NOT NULL, 
	email VARCHAR(100) NOT NULL, 
	password VARCHAR(255) NOT NULL, 
	creado_en DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id), 
	FOREIGN KEY(role_id) REFERENCES roles (id), 
	UNIQUE (email)
);

CREATE TABLE comunicados (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	titulo VARCHAR(150) NOT NULL, 
	contenido TEXT NOT NULL, 
	emisor_id INTEGER, 
	fecha_publicacion DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id), 
	FOREIGN KEY(emisor_id) REFERENCES usuarios (id)
);

CREATE TABLE docentes (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	usuario_id INTEGER, 
	especialidad VARCHAR(100), 
	telefono VARCHAR(12), 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id)
);

CREATE TABLE justificaciones (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	asistencia_id INTEGER NOT NULL, 
	motivo TEXT NOT NULL, 
	fecha_solicitud DATETIME NOT NULL DEFAULT (now()), 
	estado ENUM('pendiente','aprobado','rechazado') NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(asistencia_id) REFERENCES asistencias (id)
);

CREATE TABLE padres (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	usuario_id INTEGER, 
	telefono VARCHAR(12) NOT NULL, 
	direccion TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id)
);

CREATE TABLE personas_autorizadas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	estudiante_id INTEGER NOT NULL, 
	nombre_completo VARCHAR(150) NOT NULL, 
	dni VARCHAR(10), 
	parentesco_o_relacion VARCHAR(50), 
	telefono VARCHAR(12), 
	registrado_por_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(estudiante_id) REFERENCES estudiantes (id), 
	FOREIGN KEY(registrado_por_id) REFERENCES usuarios (id)
);

CREATE TABLE aulas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	grado_id INTEGER NOT NULL, 
	seccion VARCHAR(10) NOT NULL, 
	capacidad_maxima INTEGER NOT NULL, 
	tutor_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(grado_id) REFERENCES grados (id), 
	FOREIGN KEY(tutor_id) REFERENCES docentes (id)
);

CREATE TABLE entrada_salida (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	estudiante_id INTEGER NOT NULL, 
	fecha_hora DATETIME NOT NULL DEFAULT (now()), 
	tipo ENUM('entrada','salida') NOT NULL, 
	persona_autorizada_id INTEGER, 
	detalle VARCHAR(200), 
	PRIMARY KEY (id), 
	FOREIGN KEY(estudiante_id) REFERENCES estudiantes (id), 
	FOREIGN KEY(persona_autorizada_id) REFERENCES personas_autorizadas (id)
);

CREATE TABLE estudiante_padre (
	estudiante_id INTEGER NOT NULL, 
	padre_id INTEGER NOT NULL, 
	parentesco VARCHAR(50), 
	PRIMARY KEY (estudiante_id, padre_id), 
	FOREIGN KEY(estudiante_id) REFERENCES estudiantes (id), 
	FOREIGN KEY(padre_id) REFERENCES padres (id)
);

CREATE TABLE asignaciones_docente (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	docente_id INTEGER NOT NULL, 
	aula_id INTEGER NOT NULL, 
	area_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_aula_area UNIQUE (aula_id, area_id), 
	FOREIGN KEY(docente_id) REFERENCES docentes (id), 
	FOREIGN KEY(aula_id) REFERENCES aulas (id), 
	FOREIGN KEY(area_id) REFERENCES areas (id)
);

CREATE TABLE matriculas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	estudiante_id INTEGER NOT NULL, 
	aula_id INTEGER NOT NULL, 
	anio_lectivo INTEGER NOT NULL, 
	estado VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_matricula_anio UNIQUE (estudiante_id, anio_lectivo), 
	FOREIGN KEY(estudiante_id) REFERENCES estudiantes (id), 
	FOREIGN KEY(aula_id) REFERENCES aulas (id)
);

CREATE TABLE calificaciones (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	matricula_id INTEGER NOT NULL, 
	competencia_id INTEGER NOT NULL, 
	bimestre INTEGER NOT NULL, 
	nivel_logro ENUM('AD','A','B','C') NOT NULL, 
	registrado_por_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_calif UNIQUE (matricula_id, competencia_id, bimestre), 
	FOREIGN KEY(matricula_id) REFERENCES matriculas (id), 
	FOREIGN KEY(competencia_id) REFERENCES competencias (id), 
	FOREIGN KEY(registrado_por_id) REFERENCES usuarios (id)
);

CREATE TABLE conclusiones_descriptivas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	matricula_id INTEGER NOT NULL, 
	area_id INTEGER NOT NULL, 
	bimestre INTEGER NOT NULL, 
	texto TEXT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_conclusion UNIQUE (matricula_id, area_id, bimestre), 
	FOREIGN KEY(matricula_id) REFERENCES matriculas (id), 
	FOREIGN KEY(area_id) REFERENCES areas (id)
);

CREATE TABLE evaluaciones_conducta (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	matricula_id INTEGER NOT NULL, 
	bimestre INTEGER NOT NULL, 
	comportamiento ENUM('AD','A','B','C') NOT NULL, 
	puntualidad ENUM('AD','A','B','C') NOT NULL, 
	presentacion_personal ENUM('AD','A','B','C') NOT NULL, 
	registrado_por_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_conducta UNIQUE (matricula_id, bimestre), 
	FOREIGN KEY(matricula_id) REFERENCES matriculas (id), 
	FOREIGN KEY(registrado_por_id) REFERENCES usuarios (id)
);
