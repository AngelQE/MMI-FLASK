"""
Modelos ORM (SQLAlchemy) - Sistema Mi Mundo Infantil
Basado en el Reglamento Interno 2026 de la I.E.P. Mi Mundo Infantil:

  * 2 niveles: INICIAL (3, 4 y 5 años - ciclo II) y PRIMARIA (1° a 6° - ciclos III, IV y V)
  * Cada grado tiene edad normativa, edad máxima de acceso y horario propio (Anexo 2, Art. 69)
  * Cada aula tiene capacidad máxima (Art. 82)
  * Se evalúa por COMPETENCIA con escala literal AD / A / B / C, cada BIMESTRE (Art. 131-132)
  * La conducta la evalúa el tutor con la misma escala (Art. 135-136)
"""
from datetime import date, datetime, time
from typing import Optional, List
import enum

import secrets
import string

from sqlalchemy import (
    String, Text, Date, DateTime, Time, Integer, Boolean, ForeignKey,
    UniqueConstraint, Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from db import engine


#Generador de id automatico

def generar_id() -> str:
    caracteres = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(caracteres) for _ in range(8))


class Base(DeclarativeBase):
    pass


def _enum(cls):
    """Guarda en la BD el texto del enum (ej. 'AD'), no el nombre interno de Python."""
    return SAEnum(cls, values_callable=lambda x: [e.value for e in x])


# ============================================================
# ENUMS
# ============================================================
class Nivel(enum.Enum):
    inicial = "inicial"
    primaria = "primaria"


class NivelLogro(enum.Enum):
    """Escala literal del Art. 131 del Reglamento Interno."""
    AD = "AD"   # Logro destacado
    A = "A"     # Logro esperado
    B = "B"     # En proceso
    C = "C"     # En inicio


DESCRIPCION_LOGRO = {
    "AD": "Logro destacado",
    "A": "Logro esperado",
    "B": "En proceso",
    "C": "En inicio",
}


class EstadoAsistencia(enum.Enum):
    presente = "presente"
    ausente = "ausente"
    tardanza = "tardanza"
    justificado = "justificado"


class EstadoJustificacion(enum.Enum):
    pendiente = "pendiente"
    aprobado = "aprobado"
    rechazado = "rechazado"


class TipoMovimiento(enum.Enum):
    entrada = "entrada"
    salida = "salida"


# ============================================================
# ROLES Y USUARIOS
# ============================================================
class Rol(Base):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text)

    usuarios: Mapped[List["Usuario"]] = relationship(back_populates="rol")


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    role_id: Mapped[Optional[str]] = mapped_column(String(8), ForeignKey("roles.id"))
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    rol: Mapped[Optional["Rol"]] = relationship(back_populates="usuarios")
    padre: Mapped[Optional["Padre"]] = relationship(back_populates="usuario", uselist=False, cascade="all, delete-orphan")
    docente: Mapped[Optional["Docente"]] = relationship(back_populates="usuario", uselist=False, cascade="all, delete-orphan")


class Docente(Base):
    __tablename__ = "docentes"
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    usuario_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"))
    especialidad: Mapped[Optional[str]] = mapped_column(String(100))
    telefono: Mapped[Optional[str]] = mapped_column(String(12))

    usuario: Mapped[Optional["Usuario"]] = relationship(back_populates="docente")
    aulas_a_cargo: Mapped[List["Aula"]] = relationship(back_populates="tutor")
    asignaciones: Mapped[List["AsignacionDocente"]] = relationship(back_populates="docente", cascade="all, delete-orphan")


class Padre(Base):
    __tablename__ = "padres"
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    usuario_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"))
    telefono: Mapped[str] = mapped_column(String(12), nullable=False)
    direccion: Mapped[Optional[str]] = mapped_column(Text)

    usuario: Mapped[Optional["Usuario"]] = relationship(back_populates="padre")
    hijos: Mapped[List["EstudiantePadre"]] = relationship(back_populates="padre", cascade="all, delete-orphan")


# ============================================================
# ESTRUCTURA ACADÉMICA: nivel -> grado -> aula
# ============================================================
class Grado(Base):
    __tablename__ = "grados"
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    nivel: Mapped[Nivel] = mapped_column(_enum(Nivel), nullable=False)
    nombre: Mapped[str] = mapped_column(String(30), nullable=False)       # "3 años", "1° grado"
    ciclo: Mapped[str] = mapped_column(String(5), nullable=False)         # "II", "III"...
    edad_normativa: Mapped[int] = mapped_column(Integer, nullable=False)
    edad_maxima: Mapped[int] = mapped_column(Integer, nullable=False)     # edad máxima para acceder (Anexo 2)
    hora_ingreso: Mapped[time] = mapped_column(Time, nullable=False)
    hora_salida: Mapped[time] = mapped_column(Time, nullable=False)

    aulas: Mapped[List["Aula"]] = relationship(back_populates="grado", cascade="all, delete-orphan")


class Aula(Base):
    __tablename__ = "aulas"
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    grado_id: Mapped[str] = mapped_column(String(8), ForeignKey("grados.id"), nullable=False)
    seccion: Mapped[str] = mapped_column(String(10), default="Única")
    capacidad_maxima: Mapped[int] = mapped_column(Integer, nullable=False)
    tutor_id: Mapped[Optional[str]] = mapped_column(String(8), ForeignKey("docentes.id"))

    grado: Mapped["Grado"] = relationship(back_populates="aulas")
    tutor: Mapped[Optional["Docente"]] = relationship(back_populates="aulas_a_cargo")
    matriculas: Mapped[List["Matricula"]] = relationship(back_populates="aula")
    asignaciones: Mapped[List["AsignacionDocente"]] = relationship(back_populates="aula", cascade="all, delete-orphan")

    @property
    def nombre(self) -> str:
        if self.seccion and self.seccion != "Única":
            return f"{self.grado.nombre} - Sección {self.seccion}"
        return self.grado.nombre


class Area(Base):
    """Área curricular (lo que antes llamábamos 'curso')."""
    __tablename__ = "areas"
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    nivel: Mapped[Nivel] = mapped_column(_enum(Nivel), nullable=False)
    es_transversal: Mapped[bool] = mapped_column(Boolean, default=False)

    competencias: Mapped[List["Competencia"]] = relationship(back_populates="area", cascade="all, delete-orphan")


class Competencia(Base):
    __tablename__ = "competencias"
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    area_id: Mapped[str] = mapped_column(String(8), ForeignKey("areas.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(250), nullable=False)

    area: Mapped["Area"] = relationship(back_populates="competencias")


class AsignacionDocente(Base):
    """Qué docente enseña qué área en qué aula (además del tutor, que ve todas)."""
    __tablename__ = "asignaciones_docente"
    __table_args__ = (UniqueConstraint("aula_id", "area_id", name="uq_aula_area"),)
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    docente_id: Mapped[str] = mapped_column(String(8), ForeignKey("docentes.id"), nullable=False)
    aula_id: Mapped[str] = mapped_column(String(8),ForeignKey("aulas.id"), nullable=False)
    area_id: Mapped[str] = mapped_column(String(8),ForeignKey("areas.id"), nullable=False)

    docente: Mapped["Docente"] = relationship(back_populates="asignaciones")
    aula: Mapped["Aula"] = relationship(back_populates="asignaciones")
    area: Mapped["Area"] = relationship()


# ============================================================
# ESTUDIANTES, PADRES Y SEGURIDAD
# ============================================================
class Estudiante(Base):
    __tablename__ = "estudiantes"
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    fecha_nacimiento: Mapped[date] = mapped_column(Date, nullable=False)
    dni_documento: Mapped[Optional[str]] = mapped_column(String(10), unique=True)
    tiene_nee: Mapped[bool] = mapped_column(Boolean, default=False)            # necesidades educativas especiales
    salida_autonoma: Mapped[bool] = mapped_column(Boolean, default=False)      # Art. 76: solo con autorización escrita

    padres: Mapped[List["EstudiantePadre"]] = relationship(back_populates="estudiante", cascade="all, delete-orphan")
    matriculas: Mapped[List["Matricula"]] = relationship(back_populates="estudiante", cascade="all, delete-orphan")
    asistencias: Mapped[List["Asistencia"]] = relationship(back_populates="estudiante", cascade="all, delete-orphan")
    entradas_salidas: Mapped[List["EntradaSalida"]] = relationship(back_populates="estudiante", cascade="all, delete-orphan")
    personas_autorizadas: Mapped[List["PersonaAutorizada"]] = relationship(back_populates="estudiante", cascade="all, delete-orphan")

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}"

    def edad_al_31_marzo(self, anio):
        """El reglamento cuenta la edad cronológica al 31 de marzo del año de matrícula."""
        ref = date(int(anio), 3, 31)
        n = self.fecha_nacimiento
        return ref.year - n.year - ((ref.month, ref.day) < (n.month, n.day))


class EstudiantePadre(Base):
    __tablename__ = "estudiante_padre"
    estudiante_id: Mapped[str] = mapped_column(String(8), ForeignKey("estudiantes.id"), primary_key=True)
    padre_id: Mapped[str] = mapped_column(String(8), ForeignKey("padres.id"), primary_key=True)
    parentesco: Mapped[Optional[str]] = mapped_column(String(50))

    estudiante: Mapped["Estudiante"] = relationship(back_populates="padres")
    padre: Mapped["Padre"] = relationship(back_populates="hijos")


class PersonaAutorizada(Base):
    """Art. 72: el padre comunica por escrito quiénes pueden recoger al estudiante."""
    __tablename__ = "personas_autorizadas"
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    estudiante_id: Mapped[str] = mapped_column(String(8), ForeignKey("estudiantes.id"), nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    dni: Mapped[Optional[str]] = mapped_column(String(10))
    parentesco_o_relacion: Mapped[Optional[str]] = mapped_column(String(50))
    telefono: Mapped[Optional[str]] = mapped_column(String(12))
    registrado_por_id: Mapped[Optional[str]] = mapped_column(String(8), ForeignKey("usuarios.id"))

    estudiante: Mapped["Estudiante"] = relationship(back_populates="personas_autorizadas")


# ============================================================
# MATRÍCULA
# ============================================================
class Matricula(Base):
    __tablename__ = "matriculas"
    __table_args__ = (UniqueConstraint("estudiante_id", "anio_lectivo", name="uq_matricula_anio"),)
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    estudiante_id: Mapped[str] = mapped_column(String(8), ForeignKey("estudiantes.id"), nullable=False)
    aula_id: Mapped[str] = mapped_column(String(8), ForeignKey("aulas.id"), nullable=False)
    anio_lectivo: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), default="activo")

    estudiante: Mapped["Estudiante"] = relationship(back_populates="matriculas")
    aula: Mapped["Aula"] = relationship(back_populates="matriculas")
    calificaciones: Mapped[List["Calificacion"]] = relationship(back_populates="matricula", cascade="all, delete-orphan")
    conclusiones: Mapped[List["ConclusionDescriptiva"]] = relationship(back_populates="matricula", cascade="all, delete-orphan")
    conductas: Mapped[List["EvaluacionConducta"]] = relationship(back_populates="matricula", cascade="all, delete-orphan")


# ============================================================
# EVALUACIÓN (escala literal AD/A/B/C por competencia y bimestre)
# ============================================================
class Calificacion(Base):
    __tablename__ = "calificaciones"
    __table_args__ = (UniqueConstraint("matricula_id", "competencia_id", "bimestre", name="uq_calif"),)
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    matricula_id: Mapped[str] = mapped_column(String(8), ForeignKey("matriculas.id"), nullable=False)
    competencia_id: Mapped[str] = mapped_column(String(8), ForeignKey("competencias.id"), nullable=False)
    bimestre: Mapped[int] = mapped_column(Integer, nullable=False)     # 1 a 4
    nivel_logro: Mapped[NivelLogro] = mapped_column(_enum(NivelLogro), nullable=False)
    registrado_por_id: Mapped[Optional[str]] = mapped_column(String(8), ForeignKey("usuarios.id"))

    matricula: Mapped["Matricula"] = relationship(back_populates="calificaciones")
    competencia: Mapped["Competencia"] = relationship()


class ConclusionDescriptiva(Base):
    """Art. 132-133: conclusión descriptiva del avance del estudiante en un área, por bimestre."""
    __tablename__ = "conclusiones_descriptivas"
    __table_args__ = (UniqueConstraint("matricula_id", "area_id", "bimestre", name="uq_conclusion"),)
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    matricula_id: Mapped[str] = mapped_column(String(8), ForeignKey("matriculas.id"), nullable=False)
    area_id: Mapped[str] = mapped_column(String(8), ForeignKey("areas.id"), nullable=False)
    bimestre: Mapped[int] = mapped_column(Integer, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)

    matricula: Mapped["Matricula"] = relationship(back_populates="conclusiones")
    area: Mapped["Area"] = relationship()


class EvaluacionConducta(Base):
    """Art. 135-136: la evalúa el tutor en 3 rubros, cada bimestre."""
    __tablename__ = "evaluaciones_conducta"
    __table_args__ = (UniqueConstraint("matricula_id", "bimestre", name="uq_conducta"),)
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    matricula_id: Mapped[str] = mapped_column(String(8), ForeignKey("matriculas.id"), nullable=False)
    bimestre: Mapped[int] = mapped_column(Integer, nullable=False)
    comportamiento: Mapped[NivelLogro] = mapped_column(_enum(NivelLogro), nullable=False)
    puntualidad: Mapped[NivelLogro] = mapped_column(_enum(NivelLogro), nullable=False)
    presentacion_personal: Mapped[NivelLogro] = mapped_column(_enum(NivelLogro), nullable=False)
    registrado_por_id: Mapped[Optional[str]] = mapped_column(String(8), ForeignKey("usuarios.id"))

    matricula: Mapped["Matricula"] = relationship(back_populates="conductas")


# ============================================================
# ASISTENCIA, JUSTIFICACIONES, ENTRADA / SALIDA
# ============================================================
class Asistencia(Base):
    __tablename__ = "asistencias"
    __table_args__ = (UniqueConstraint("estudiante_id", "fecha", name="uq_asistencia_dia"),)
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    estudiante_id: Mapped[str] = mapped_column(String(8), ForeignKey("estudiantes.id"), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    estado: Mapped[EstadoAsistencia] = mapped_column(_enum(EstadoAsistencia), nullable=False)

    estudiante: Mapped["Estudiante"] = relationship(back_populates="asistencias")
    justificaciones: Mapped[List["Justificacion"]] = relationship(back_populates="asistencia", cascade="all, delete-orphan")


class Justificacion(Base):
    __tablename__ = "justificaciones"
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    asistencia_id: Mapped[str] = mapped_column(String(8), ForeignKey("asistencias.id"), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_solicitud: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    estado: Mapped[EstadoJustificacion] = mapped_column(_enum(EstadoJustificacion), default=EstadoJustificacion.pendiente)

    asistencia: Mapped["Asistencia"] = relationship(back_populates="justificaciones")


class EntradaSalida(Base):
    __tablename__ = "entrada_salida"
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("estudiantes.id"), nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    tipo: Mapped[TipoMovimiento] = mapped_column(_enum(TipoMovimiento), nullable=False)
    persona_autorizada_id: Mapped[Optional[int]] = mapped_column(ForeignKey("personas_autorizadas.id"))
    detalle: Mapped[Optional[str]] = mapped_column(String(200))   # "Retirado por su madre", "Salida autónoma autorizada"...

    estudiante: Mapped["Estudiante"] = relationship(back_populates="entradas_salidas")
    persona_autorizada: Mapped[Optional["PersonaAutorizada"]] = relationship()


# ============================================================
# COMUNICADOS
# ============================================================
class Comunicado(Base):
    __tablename__ = "comunicados"
    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generar_id )
    titulo: Mapped[str] = mapped_column(String(150), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    emisor_id: Mapped[Optional[str]] = mapped_column(String(8), ForeignKey("usuarios.id"))
    fecha_publicacion: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    emisor: Mapped[Optional["Usuario"]] = relationship()


Base.metadata.create_all(engine)
