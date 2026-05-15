# DeepSeek API — Análisis de confidencialidad y riesgo regulatorio

**Fecha de investigación:** 15 de mayo de 2026  
**Metodología:** Revisión de documentos oficiales de DeepSeek (política de privacidad y términos del open platform, vigentes a marzo 2026), legislación china primaria, informes de autoridades reguladoras europeas (IAPP, Garante, EDPB), análisis técnicos de NowSecure, Wiz y Theori, y análisis legal de Ropes & Gray. Las afirmaciones se atribuyen a su fuente; las inferencias se marcan explícitamente.

---

## 1. Lo que DeepSeek declara sobre confidencialidad

- **Controlador de datos:** Hangzhou DeepSeek Artificial Intelligence Co., Ltd., con sede en China. *(Fuente: política de privacidad oficial, marzo 2026)*
- **Uso de inputs y outputs:** DeepSeek se reserva el derecho a usar los datos enviados a su plataforma para "proveer, mantener, operar, desarrollar o mejorar" sus servicios. Los propios términos advierten de que no existe expectativa razonable de control exclusivo sobre los inputs. *(Fuente: Ropes & Gray, análisis de términos, enero 2025)*
- **Compartición con terceros:** La política permite compartir datos con socios publicitarios, entidades del grupo corporativo y terceros en transacciones corporativas, sin especificar el alcance. *(Fuente: política de privacidad oficial; análisis Digiday, enero 2025)*
- **Responsabilidad en la API:** Los términos del open platform trasladan al desarrollador integrador la responsabilidad de implementar controles de seguridad, monitoreo y gestión de usuarios. DeepSeek no asume esa carga. *(Fuente: DeepSeek Open Platform Terms of Service, marzo 2026)*

**Valoración:** Las declaraciones de confidencialidad son genéricas. La ausencia de Standard Contractual Clauses (SCCs) para transferencias fuera de China y la falta de un compromiso explícito de no utilizar datos de clientes API para entrenamiento son omisiones materiales en comparación con proveedores occidentales equivalentes.

---

## 2. Hallazgos técnicos independientes

| Hallazgo | Fuente | Fecha |
|---|---|---|
| Base de datos ClickHouse expuesta públicamente sin autenticación, con historial de chats, claves API y metadatos de backend | Wiz Research | Enero 2025 |
| App móvil: transmisión de datos sin cifrar, 3DES con claves hardcoded, iOS App Transport Security deshabilitado | NowSecure | Enero 2025 |
| Conexiones no declaradas con Volcengine, plataforma cloud de ByteDance | NowSecure | Enero 2025 |
| Vulnerabilidades SQL injection y mecanismos anti-debugging | SecurityScorecard STRIKE Team | Enero 2025 |

**Observación:** La brecha entre las declaraciones de privacidad de DeepSeek y los controles técnicos encontrados en auditorías independientes es relevante para evaluar la credibilidad de sus garantías. Esto no implica mala fe comprobada, pero sí ausencia de controles auditables que respalden lo declarado.

---

## 3. Marco legal chino: obligación de cooperar con el Estado

**Texto legal aplicable (fuente primaria: chinalawtranslate.com, texto oficial PRC):**

- **Artículo 7, Ley de Inteligencia Nacional (2017, enmendada 2018):** "Todas las organizaciones y ciudadanos deberán apoyar, asistir y cooperar con los esfuerzos de inteligencia nacional de acuerdo con la ley."
- **Artículo 14:** Las instituciones de inteligencia estatal pueden requerir a organizaciones o ciudadanos que proporcionen el apoyo y cooperación necesarios durante el ejercicio legal de sus funciones.

**Debate jurídico existente:**  
El investigador Jeremy Daum (China Law Translate, 2024) argumenta que el Art. 7 carece de mecanismo de aplicación propio, que las sanciones solo se activan al "obstaculizar" el trabajo de inteligencia, y que dicho trabajo debe conducirse "de acuerdo con la ley", lo que podría incluir restricciones de la PIPL (ley de protección de datos china). Este argumento es legítimo y está documentado.

**Posición contraria:** El DHS de EE.UU. y múltiples analistas de seguridad sostienen que el marco legal chino obliga a las empresas a cooperar en secreto con los servicios de inteligencia incluso cuando esa cooperación sea ilegal en la jurisdicción donde operan, y a mantener esa cooperación confidencial. *(Fuente: DHS Data Security Business Advisory, 2020; The Diplomat, 2019)*

**Valoración neutral:** El debate sobre el alcance exacto del Art. 7 es real entre juristas. Lo que no está en disputa es que (a) no existe ningún mecanismo legal que *impida* al Estado chino solicitar los datos, y (b) sí existe uno que *obliga* a la empresa a mantener esa eventual solicitud en secreto. La ausencia de evidencia pública de que esto haya ocurrido con DeepSeek es coherente con el diseño del propio marco legal.

---

## 4. Respuesta regulatoria global (estado a mayo 2026)

- **Italia:** Garante bloqueó el servicio en enero 2025 (72 horas tras el lanzamiento global); calificó la respuesta de DeepSeek a su requerimiento de datos como "completamente insuficiente". *(Fuente: IAPP, febrero 2026)*
- **Europa:** Investigaciones abiertas en 13 jurisdicciones. El EDPB creó un grupo de trabajo específico de IA. Autoridades de Berlín, Países Bajos y otros señalaron la transferencia de datos a "procesadores chinos" en China sin mecanismo de adecuación GDPR. *(Fuente: IAPP, febrero 2026)*
- **Australia:** Prohibición en todos los dispositivos gubernamentales (febrero 2025), citando "nivel inaceptable de riesgo para la seguridad nacional". *(Fuente: Department of Home Affairs)*
- **EE.UU.:** Prohibiciones en el Pentágono, NASA, Marina, y propuesta legislativa H.R.1121 (119.º Congreso) para prohibir DeepSeek en dispositivos gubernamentales. *(Fuente: Congress.gov, 2025)*
- **República Checa:** Uso prohibido en administración pública, incluidos APIs, desde julio 2025. *(Fuente: registros regulatorios, julio 2025)*
- **España/UE:** A mayo 2026, no consta prohibición para usuarios privados, pero el uso en el sector público está bajo escrutinio activo del marco GDPR.

---

## 5. Distinción crítica: API cloud vs. modelo local

| Modalidad | Exposición de datos | Riesgo regulatorio |
|---|---|---|
| **API cloud de DeepSeek** | Datos enviados a servidores en China | Alto: aplica todo lo anterior |
| **Modelo open-source en infraestructura propia** | Sin transferencia a DeepSeek | Bajo: comparable a cualquier LLM open-source |
| **Modelo DeepSeek en proveedor cloud UE/EE.UU.** (ej. Perplexity, Azure) | Datos en servidores del proveedor, no en China | Medio: depende de los términos del proveedor intermediario |

---

## 6. Síntesis

| Dimensión | Situación a 15/05/2026 |
|---|---|
| Confidencialidad declarada por DeepSeek | Genérica, con cesiones amplias a terceros y para entrenamiento |
| Controles técnicos verificados | Historial de vulnerabilidades graves; auditorías independientes negativas |
| Obligación legal de cooperar con Estado chino | Marco legal existe; su alcance exacto es debatido entre juristas |
| Respuesta regulatoria occidental | Prohibiciones en sector público en múltiples países; GDPR sin resolución definitiva |
| Uso empresarial con datos sensibles vía API cloud | No recomendado por reguladores ni por análisis de riesgo independientes |

---

*Fuentes primarias: DeepSeek Privacy Policy y Open Platform Terms (marzo 2026); PRC National Intelligence Law (2017/2018) vía chinalawtranslate.com; IAPP (febrero 2026); Ropes & Gray (enero 2025); NowSecure; Wiz Research; DHS Data Security Advisory (2020); Garante (enero 2025).*

---

---

# Especificación: Bloqueador / Anonimizador de datos sensibles para entornos corporativos bancarios

**Contexto de uso:** Interceptor de payload situado entre el código del desarrollador y cualquier llamada a la API de DeepSeek (u otro LLM externo). Opera sobre texto libre, documentos estructurados y desestructurados, queries SQL y fragmentos de código fuente.

**Principio de diseño base:** Denegación por defecto. Si un patrón es ambiguo, se enmascara. La pérdida de utilidad por falso positivo es recuperable; la fuga de un dato sensible, no.

---

## Categoría 1 — Identidad personal (PII clásica, GDPR Art. 4)

| Dato | Patrón de detección | Alias sugerido |
|---|---|---|
| Nombre completo (persona física) | NER + patrones `Apellido, Nombre` / `Nombre Apellido` en contexto nominal | `[PERSONA_1]` |
| DNI español | `\d{8}[A-Z]` con validación de letra de control | `[DNI_1]` |
| NIE español | `[XYZ]\d{7}[A-Z]` con validación | `[NIE_1]` |
| Pasaporte (ES y EU) | Patrones por país + longitud + contexto "pasaporte/passport" | `[PASAPORTE_1]` |
| Número de seguridad social (NAF) | `\d{2}[\/ ]\d{8}[\/ ]\d{2}` | `[NSS_1]` |
| Fecha de nacimiento | Fechas en contexto biográfico o campo `fecha_nacimiento`, `dob`, `birthdate` | `[FECHA_NAC_1]` |
| Dirección postal | NER + patrones `Calle/C\./Av\..*\d+` + CP + municipio | `[DIRECCION_1]` |
| Código postal | `\d{5}` en contexto de dirección | `[CP_1]` |
| Teléfono (ES y internacional) | `(\+34\|0034)?[\s\-]?[6-9]\d{8}` / E.164 | `[TEL_1]` |
| Email personal | RFC 5322 + dominios no corporativos conocidos | `[EMAIL_PERSONAL_1]` |
| Email corporativo | RFC 5322 + dominio interno de la organización (configurable) | `[EMAIL_CORP_1]` |
| Firma escaneada / imagen con nombre | Detección de imagen embebida en doc + OCR si aplica | `[FIRMA_1]` |

---

## Categoría 2 — Credenciales y secretos técnicos

| Dato | Patrón de detección | Alias sugerido |
|---|---|---|
| API keys genéricas | Entropía alta (Shannon > 4.5) en strings de 20-80 chars alfanuméricos | `[API_KEY_1]` |
| Claves con prefijo conocido | `sk-`, `pk-`, `Bearer `, `token:`, `apikey=` + valor | `[SECRET_TOKEN_1]` |
| Passwords en texto plano | Campos `password`, `passwd`, `pwd`, `contraseña`, `clave` + `=`, `:` + valor | `[PASSWORD_1]` |
| Connection strings (JDBC/ODBC) | `jdbc:`, `Server=`, `Data Source=`, `mongodb://`, `postgres://` con credenciales | `[CONN_STRING_1]` |
| Claves privadas (PEM) | `-----BEGIN (RSA\|EC\|OPENSSH) PRIVATE KEY-----` | `[PRIVATE_KEY_1]` |
| Certificados X.509 | `-----BEGIN CERTIFICATE-----` | `[CERT_1]` |
| JWT tokens | `eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+` | `[JWT_1]` |
| OAuth / Bearer tokens | `Bearer [A-Za-z0-9\-._~+\/]+=*` en headers | `[BEARER_1]` |
| Hashes de contraseña | `\$2[aby]\$`, `\$argon2`, `{SHA}`, `{SSHA}` + valor | `[HASH_CRED_1]` |
| Secretos en variables de entorno | `export SECRET=`, `ENV[...]=`, `.env` key=value con entropía alta | `[ENV_SECRET_1]` |
| Webhooks con token embebido | URLs con path que contiene token de alta entropía | `[WEBHOOK_URL_1]` |

---

## Categoría 3 — Datos bancarios y financieros

| Dato | Patrón de detección | Alias sugerido |
|---|---|---|
| IBAN (todos los países) | `[A-Z]{2}\d{2}[A-Z0-9]{4,30}` + validación módulo 97 | `[IBAN_1]` |
| Número de tarjeta (PAN) | `\d{13,19}` agrupado o no + validación algoritmo de Luhn | `[PAN_1]` |
| CVV/CVC | 3-4 dígitos en contexto de campo `cvv`, `cvc`, `security_code` | `[CVV_1]` |
| Fecha de expiración tarjeta | `(0[1-9]\|1[0-2])\/\d{2,4}` en contexto de pago | `[EXP_TARJETA_1]` |
| SWIFT/BIC | `[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?` + contexto bancario | `[BIC_1]` |
| NIF/CIF empresa | `[A-Z]\d{7}[A-Z0-9]` con validación de dígito de control | `[CIF_1]` |
| Número de préstamo/hipoteca | Patrones internos configurables + contexto `préstamo`, `hipoteca`, `operación` | `[NUM_OP_1]` |
| Importes con contexto sensible | Cifras monetarias asociadas a persona o contrato identificado | `[IMPORTE_1]` |
| Número de cuenta nacional (CCC) | `\d{4}[\s\-]\d{4}[\s\-]\d{2}[\s\-]\d{10}` | `[CCC_1]` |
| Datos de movimientos bancarios | Filas con fecha + concepto + importe + contrapartida nominal | `[MOVIMIENTO_1]` |

---

## Categoría 4 — Infraestructura y arquitectura interna

| Dato | Patrón de detección | Alias sugerido |
|---|---|---|
| IPs privadas (RFC 1918) | `10\.`, `172\.(1[6-9]\|2\d\|3[01])\.`, `192\.168\.` | `[IP_INTERNA_1]` |
| IPs públicas de producción | Lista blanca inversa: IPs no reconocidas como CDN/pública genérica | `[IP_PROD_1]` |
| Hostnames internos | `[a-z0-9\-]+\.(internal\|corp\|local\|intranet\|lan)` + dominios configurables | `[HOST_1]` |
| URLs de endpoints internos | Protocolo + hostname interno + path, especialmente con `/api/`, `/admin/`, `/v\d/` | `[URL_INTERNA_1]` |
| Nombres de bases de datos | Contexto `database=`, `catalog=`, `schema=` + valor no genérico | `[DB_NAME_1]` |
| Nombres de tablas sensibles | Lista configurable: `clientes`, `accounts`, `usuarios`, `transactions`, `riesgo`... | `[TABLE_1]` |
| MAC addresses | `([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}` | `[MAC_1]` |
| Números de puerto en contexto de host interno | Host + `:` + puerto no estándar (no 80/443) | `[PUERTO_1]` |
| Rutas del sistema de ficheros internas | `/home/`, `/var/`, `C:\Users\`, `\\servidor\` con nombre de usuario o proyecto | `[PATH_1]` |

---

## Categoría 5 — Documentos legales y contratos

| Dato | Patrón de detección | Alias sugerido |
|---|---|---|
| Nombre de contraparte contractual | NER en contexto `entre [ENTIDAD] y [ENTIDAD]`, cabeceras de contrato | `[CONTRAPARTE_1]` |
| Número de contrato / expediente | Patrones internos configurables + contexto `contrato nº`, `expediente`, `ref.` | `[NUM_CONTRATO_1]` |
| Importes contractuales | Cifras en contexto de `importe`, `precio`, `valor`, `retribución` en documento legal | `[IMPORTE_CONTRATO_1]` |
| Fechas de vigencia | Fechas en cláusulas `entrada en vigor`, `vencimiento`, `renovación` | `[FECHA_CONTRATO_1]` |
| Datos del notario / registro | Nombre de notario, número de protocolo, registro mercantil | `[NOTARIO_1]` |
| Cláusulas de confidencialidad con contenido específico | Párrafos que citan expresamente información protegida por acuerdo NDA | `[CLAUSULA_CONF_1]` |
| Datos de representante legal | Nombre + DNI + cargo en contexto de apoderado/firmante | `[REP_LEGAL_1]` |

---

## Categoría 6 — Queries SQL y esquemas de base de datos

| Dato | Patrón de detección | Alias sugerido |
|---|---|---|
| Valores literales en WHERE/INSERT/UPDATE | Strings y números entre comillas o sin ellas en posiciones de valor | `[SQL_VAL_1]` |
| Nombres de tablas en lista configurable | `FROM tabla_sensible`, `JOIN tabla_sensible` | `[SQL_TABLE_1]` |
| Nombres de columnas sensibles | `SELECT nombre, apellido, iban, saldo...` → columnas de lista configurable | `[SQL_COL_1]` |
| Connection strings embebidos en SQL | `OPENROWSET`, `LINKED SERVER` con credenciales | `[SQL_CONN_1]` |
| Stored procedures con lógica propietaria | Cuerpo completo de SP con nombre en lista negra configurada | `[SP_BODY_1]` |
| Comentarios SQL con info operativa | `--` y `/* */` con IPs, nombres, contraseñas, referencias a entornos | `[SQL_COMMENT_1]` |
| EXEC con parámetros literales sensibles | `EXEC sp_nombre 'valor_sensible'` | `[SQL_EXEC_1]` |

---

## Categoría 7 — Código fuente

| Dato | Patrón de detección | Alias sugerido |
|---|---|---|
| Credenciales hardcodeadas | Variables `password`, `secret`, `api_key`, `token` con asignación de valor literal | `[CODE_CRED_1]` |
| URLs de producción hardcodeadas | `https://[hostname interno o de producción]/` en strings de código | `[CODE_URL_1]` |
| Comentarios con datos operativos | `//`, `#`, `/* */` con IPs, nombres de usuarios, referencias a clientes | `[CODE_COMMENT_1]` |
| Lógica de scoring / modelos de riesgo propietarios | Funciones con nombres en lista negra configurable (ej. `calcular_riesgo_crediticio`) | `[CODE_LOGIC_1]` |
| Datos de test hardcodeados | DNIs, IBANs, correos reales usados como fixtures en tests | `[TEST_DATA_1]` |
| Stack traces con rutas internas | Excepciones con `at com.empresa.` + rutas de servidor | `[STACK_TRACE_1]` |
| Logs con datos de usuario | Líneas de log que mezclan timestamp + nivel + dato personal o credencial | `[LOG_LINE_1]` |

---

## Categoría 8 — Datos corporativos y organizativos

| Dato | Patrón de detección | Alias sugerido |
|---|---|---|
| Nombre de empleado con rol | NER + contexto `responsable`, `director`, `gestor`, `analyst` | `[EMPLEADO_1]` |
| Número de empleado / matrícula | Patrones internos configurables | `[NUM_EMPLEADO_1]` |
| Organigramas con nombres | Estructuras jerárquicas con nombres propios | `[ORGANIGRAMA_1]` |
| Nombre de cliente corporativo | NER + lista negra configurable de clientes de la entidad | `[CLIENTE_CORP_1]` |
| Número de cuenta de cliente interno | Identificadores internos de cliente (no IBAN) | `[ID_CLIENTE_1]` |
| Proyecto interno con nombre propio | Nombres de proyectos en lista configurable o NER en contexto interno | `[PROYECTO_1]` |

---

## Categoría 9 — Vectores de evasión que el anonimizador debe cubrir

Estos no son tipos de dato sino formas de representación alternativa que pueden burlar detección por regex pura:

| Vector de evasión | Ejemplo | Mecanismo de detección |
|---|---|---|
| Codificación Base64 | `NjI4NTAwMTIzNDU2Nzg5MA==` (IBAN codificado) | Decodificar, aplicar detección, reenmascarar |
| URL encoding | `password%3Dsecret123` | Decodificar URL, analizar, reenmascarar |
| Hex encoding | `\x73\x65\x63\x72\x65\x74` | Decodificar hex strings, analizar |
| Split across lines / tokens | `IBAN: ES91` + newline + `2100 0418 4502 0005 1332` | Reconstruir ventana de contexto (N líneas) |
| Separadores no estándar | `6285-0012-3456-7890` vs `6285001234567890` | Normalizar separadores antes de aplicar regex |
| Datos en JSON/XML embebido en string | `"payload": "{\"iban\":\"ES91...\"}"` | Deserializar recursivamente strings JSON/XML |
| Comentarios multilínea con datos reales | `/* cliente: Juan García, DNI: 12345678A */` | Parsear comentarios como texto plano |
| Datos en nombres de variable | `let juan_garcia_iban = ...` | NER sobre identificadores de código |
| Concatenación de strings en código | `"ES91" + "2100" + "0418..."` | Análisis de flujo estático básico |
| Texto en imágenes embebidas (PDF/DOCX) | Tabla escaneada con IBANs | OCR sobre imágenes embebidas |

---

## Requisitos transversales de implementación

**Consistencia de alias:** El mismo valor real debe mapearse siempre al mismo alias dentro de una sesión (`Juan García` → `[PERSONA_1]` en todas sus ocurrencias). La tabla de mapping debe ser efímera (en memoria, no persistida).

**Reversibilidad controlada:** Si el flujo requiere reconstruir la respuesta del LLM con datos reales (ej. rellenar una plantilla), la tabla de mapping debe permitir restitución en entorno de ejecución seguro, nunca en el lado del LLM.

**Modos de operación:**
- `STRICT`: bloquea el envío si se detecta cualquier dato de categorías 1-3 no enmascarado.
- `AUDIT`: envía con enmascaramiento pero registra en log interno qué categorías se activaron.
- `PASSTHROUGH`: solo para entornos de desarrollo con datos sintéticos (requiere flag explícito).

**Idiomas:** Detección mínima en ES y EN. Nombres propios y formatos documentales deben cubrir al menos ES, EN, FR, DE (contexto bancario europeo).

**Formatos de entrada soportados:** texto plano, JSON, XML, CSV, SQL, código fuente (Python, Java, JS, TypeScript, SQL, Shell), Markdown, HTML, PDF (vía extracción de texto), DOCX (vía extracción de texto).

---

## QA Intensivo — Suite de pruebas obligatorias

### Bloque A — Cobertura de detección (falsos negativos)

Estos tests verifican que el anonimizador **no deja pasar** datos sensibles.

| ID | Caso de prueba | Input de ejemplo | Resultado esperado |
|---|---|---|---|
| QA-A01 | IBAN con espacios | `ES91 2100 0418 4502 0005 1332` | `[IBAN_1]` |
| QA-A02 | IBAN sin espacios | `ES9121000418450200051332` | `[IBAN_1]` |
| QA-A03 | IBAN en JSON | `{"cuenta": "ES9121000418450200051332"}` | `{"cuenta": "[IBAN_1]"}` |
| QA-A04 | PAN con guiones | `4539-1488-0343-6467` + validación Luhn | `[PAN_1]` |
| QA-A05 | PAN en comentario SQL | `-- tarjeta cliente: 4539148803436467` | comentario enmascarado |
| QA-A06 | API key en variable Python | `api_key = "sk-ab12cd34ef56gh78ij90"` | `api_key = "[API_KEY_1]"` |
| QA-A07 | JWT completo en header | `Authorization: Bearer eyJhbGc...` | `Authorization: Bearer [JWT_1]` |
| QA-A08 | Contraseña en connection string | `Server=prod-db;Password=S3cr3t!;` | `Server=prod-db;Password=[PASSWORD_1];` |
| QA-A09 | IP interna en comentario | `# conectar a 192.168.1.45:5432` | `# conectar a [IP_INTERNA_1]:[PUERTO_1]` |
| QA-A10 | DNI en texto libre | `El cliente con DNI 12345678Z solicitó...` | `El cliente con DNI [DNI_1] solicitó...` |
| QA-A11 | Email en JSON anidado | `{"user": {"email": "juan@empresa.com"}}` | `{"user": {"email": "[EMAIL_CORP_1]"}}` |
| QA-A12 | IBAN en Base64 | `RVM5MTIxMDAwNDE4NDUwMjAwMDUxMzMy` (decodifica a IBAN) | `[IBAN_1]` |
| QA-A13 | Clave privada PEM | Bloque `-----BEGIN RSA PRIVATE KEY-----...` | `[PRIVATE_KEY_1]` |
| QA-A14 | Datos en WHERE clause SQL | `WHERE dni = '12345678Z'` | `WHERE dni = '[DNI_1]'` |
| QA-A15 | Nombre + cargo en texto | `La Directora de Riesgos, Ana Martínez López, aprobó...` | `La Directora de Riesgos, [PERSONA_1], aprobó...` |
| QA-A16 | Split de IBAN en líneas | `ES91` + `\n` + `210004184502` + `\n` + `00051332` | `[IBAN_1]` |
| QA-A17 | Datos en stack trace | `at com.banco.clientes.GestorDNI.validar(DNI:12345678Z)` | enmascarado |
| QA-A18 | Credencial en variable de entorno en código | `os.environ["DB_PASSWORD"] = "prod_pass_2026"` | enmascarado |
| QA-A19 | Número de tarjeta en XML | `<pan>4539148803436467</pan>` | `<pan>[PAN_1]</pan>` |
| QA-A20 | Datos de test hardcodeados en unittest | `assert iban == "ES9121000418450200051332"` | enmascarado |
| QA-A21 | CIF en factura desestructurada | `NIF: B-12345678, proveedor Empresa S.L.` | `NIF: [CIF_1], proveedor [CLIENTE_CORP_1]` |
| QA-A22 | Webhook URL con token | `https://hooks.banco.com/trigger/xK9mP2nQrS7vW4` | `[WEBHOOK_URL_1]` |
| QA-A23 | Hostname interno en URL | `http://api.core.internal/v2/accounts` | `[URL_INTERNA_1]` |
| QA-A24 | Número de teléfono en texto | `Llame al +34 612 345 678 para confirmar` | enmascarado |
| QA-A25 | Datos personales en CSV multilínea | Fichero CSV con columnas nombre, dni, iban, email | todas las columnas sensibles enmascaradas |

---

### Bloque B — Control de falsos positivos (no debe bloquear legítimo)

| ID | Caso de prueba | Input de ejemplo | Resultado esperado |
|---|---|---|---|
| QA-B01 | Número que pasa Luhn pero es ID interno | `4000000000000002` en campo `transaction_id` | no enmascarado si campo no es `pan`/`card` |
| QA-B02 | String de alta entropía que es hash SHA-256 de fichero | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` en contexto `checksum` | no enmascarado |
| QA-B03 | IP pública de CDN conocida | `1.1.1.1`, `8.8.8.8` | no enmascarado |
| QA-B04 | Fecha que no es fecha de nacimiento | `fecha_creacion: 2024-03-15` | no enmascarado |
| QA-B05 | Email de dominio público en contexto de ejemplo | `example@example.com` en documentación | configurable: enmascarar en modo STRICT |
| QA-B06 | Nombre propio que es también término técnico | clase `ClienteService` en código Java | no enmascarado (contexto de código, no nominal) |
| QA-B07 | BIC de banco público conocido | `CAIXESBBXXX` en contexto de documentación | configurable por modo |
| QA-B08 | Número de versión con formato similar a teléfono | `v6.12.345.678` | no enmascarado |
| QA-B09 | UUID de entidad no sensible | `550e8400-e29b-41d4-a716-446655440000` en contexto de `session_id` | no enmascarado por defecto |
| QA-B10 | "password" como nombre de campo en schema JSON sin valor | `"properties": {"password": {"type": "string"}}` | no enmascarado (definición, no valor) |

---

### Bloque C — Consistencia y gestión de alias

| ID | Caso de prueba | Resultado esperado |
|---|---|---|
| QA-C01 | Mismo IBAN aparece 3 veces en el documento | Las 3 instancias → mismo alias `[IBAN_1]` |
| QA-C02 | Dos IBANs distintos | `[IBAN_1]` y `[IBAN_2]` respectivamente |
| QA-C03 | Mismo nombre en formatos distintos (`Juan García` / `García, Juan`) | Mismo alias si NER los resuelve como misma entidad |
| QA-C04 | Tabla de mapping no persiste entre sesiones independientes | Nueva sesión → alias reiniciados desde `_1` |
| QA-C05 | Restitución: LLM devuelve `[IBAN_1]` en respuesta | Motor de restitución reemplaza por valor real solo en entorno seguro |
| QA-C06 | Alias no debe filtrar cardinalidad real | Si hay 47 clientes, el prompt no debe revelar ese número asociado a alias |

---

### Bloque D — Seguridad del propio anonimizador

| ID | Caso de prueba | Resultado esperado |
|---|---|---|
| QA-D01 | Log del anonimizador no contiene datos en claro | Solo alias y categoría activada, nunca el valor original |
| QA-D02 | Tabla de mapping en memoria no accesible por otros procesos | Scope estrictamente limitado a la transacción activa |
| QA-D03 | Modo PASSTHROUGH requiere flag explícito y genera alerta | No activable por configuración por defecto ni por variables de entorno sin firma |
| QA-D04 | El anonimizador no llama a ningún servicio externo | Sin telemetría, sin dependencias de red en el paso de detección |
| QA-D05 | Fallo del anonimizador bloquea el envío (fail-closed) | Si el módulo lanza excepción, la llamada a la API externa no se realiza |
| QA-D06 | Tiempo de procesamiento no revela volumen de datos sensibles vía timing attack | Tiempo de respuesta constante o añadir ruido deliberado |

---

### Bloque E — Formatos y codificaciones especiales

| ID | Caso de prueba | Resultado esperado |
|---|---|---|
| QA-E01 | IBAN en Base64 en campo JSON | Decodificar, detectar, reenmascarar codificado |
| QA-E02 | Credencial en URL encoding en query string | `%70%61%73%73%77%6F%72%64=s3cret` → enmascarado |
| QA-E03 | JSON dentro de string SQL | `INSERT INTO logs VALUES ('{"user":"12345678Z"}')` | DNI detectado dentro del JSON embebido |
| QA-E04 | XML dentro de campo CLOB en SQL | `UPDATE doc SET contenido = '<iban>ES91...</iban>'` | IBAN detectado |
| QA-E05 | DOCX con tabla que contiene IBANs | Extracción de texto de tabla + detección | enmascarado en texto extraído |
| QA-E06 | PDF escaneado (imagen) con datos sensibles | OCR + detección | enmascarado si OCR activado |
| QA-E07 | Markdown con código inline | \`password = "secret"\` | enmascarado |
| QA-E08 | CSV con delimitador no estándar (`\|` o `;`) | Parseo correcto + detección en todas las columnas | enmascarado |
| QA-E09 | IBAN en hex | `4553393132313030...` | decodificar, detectar, enmascarar |
| QA-E10 | Concatenación de IBAN en Python | `"ES91" + account_number` | marcar para revisión manual (análisis estático limitado) |

---

### Bloque F — Rendimiento y umbrales operativos

| Métrica | Umbral mínimo aceptable |
|---|---|
| Latencia p99 sobre texto < 10 KB | < 150 ms |
| Latencia p99 sobre documento 100 KB | < 800 ms |
| Tasa de falsos negativos en suite QA-A | 0% (bloqueante para release) |
| Tasa de falsos positivos en suite QA-B | < 5% (no bloqueante, pero registrado) |
| Throughput mínimo en uso concurrente | 50 req/s sin degradación |
| Cobertura de tests automáticos sobre suite QA completa | 100% en CI/CD antes de merge a main |

---

*Documento generado el 15 de mayo de 2026. Las categorías y casos de QA son exhaustivos para el contexto bancario corporativo descrito; deberán complementarse con una lista negra configurable de términos propietarios de la organización (nombres de proyectos, clientes, sistemas internos) no incluibles en un documento público.*
