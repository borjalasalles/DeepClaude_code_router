"""
Common first names and surnames by geography.

Sources: INE 2023 (Spain), INSEE (France), ISTAT (Italy), Destatis (Germany),
SSA (USA), ONS (UK), DANE (Colombia), INDEC (Argentina), INEGI (Mexico),
BFS (Switzerland).
"""
from __future__ import annotations

# ── Spain (INE 2023) ──────────────────────────────────────────────────────────

ES_MALE_NAMES: frozenset[str] = frozenset({
    "Antonio", "Manuel", "José", "Francisco", "David", "Juan", "Carlos",
    "Jesús", "Javier", "Daniel", "Pedro", "Miguel", "Rafael", "Ángel",
    "Fernando", "Luis", "Sergio", "Pablo", "Jorge", "Alejandro", "Alberto",
    "Álvaro", "Diego", "Adrián", "Mario", "Raúl", "Rubén", "Enrique",
    "Ignacio", "Iván", "Andrés", "Víctor", "Rodrigo", "Gonzalo", "Guillermo",
    "Héctor", "Felipe", "Tomás", "Ramón", "Óscar", "Santiago", "Marcos",
    "Roberto", "Eduardo", "Emilio", "Jaime", "Nicolás", "Benito", "Ricardo",
    "Agustín", "Germán", "Salvador", "Ernesto", "Arturo", "Gerardo",
})

ES_FEMALE_NAMES: frozenset[str] = frozenset({
    "María", "Carmen", "Josefa", "Isabel", "Ana", "Laura", "Cristina",
    "Marta", "Sara", "Lucía", "Manuela", "Montserrat", "Patricia", "Rosa",
    "Nuria", "Elena", "Pilar", "Paula", "Sofía", "Silvia", "Dolores",
    "Julia", "Beatriz", "Teresa", "Irene", "Natalia", "Alicia", "Raquel",
    "Sonia", "Mercedes", "Rocío", "Andrea", "Victoria", "Clara", "Claudia",
    "Inés", "Eva", "Alba", "Miriam", "Sandra", "Francisca", "Amparo",
    "Encarnación", "Concepción", "Consuelo", "Esperanza", "Remedios",
    "Antonia", "Rosario", "Dolors", "Montse", "Laia", "Núria", "Celia",
    "Noelia", "Vanessa", "Verónica", "Susana", "Mónica", "Lorena",
})

ES_SURNAMES: frozenset[str] = frozenset({
    "García", "González", "Rodríguez", "Fernández", "López", "Martínez",
    "Sánchez", "Pérez", "Gómez", "Martín", "Jiménez", "Ruiz", "Hernández",
    "Díaz", "Moreno", "Muñoz", "Álvarez", "Romero", "Alonso", "Gutiérrez",
    "Navarro", "Torres", "Domínguez", "Vázquez", "Ramos", "Gil", "Ramírez",
    "Serrano", "Blanco", "Molina", "Morales", "Suárez", "Ortega", "Delgado",
    "Castro", "Ortiz", "Rubio", "Marín", "Sanz", "Iglesias", "Medina",
    "Garrido", "Santos", "Castillo", "Cortés", "Lozano", "Guerrero", "Cano",
    "Prieto", "Méndez", "Cruz", "Calvo", "Gallego", "Herrera", "Peña",
    "Flores", "Aguilar", "Vargas", "Cabrera", "Nieto", "Pascual", "Reyes",
    "Herrero", "Vega", "Vicente", "León", "Moya", "Lorenzo", "Fuentes",
    "Caballero", "Núñez", "Ibáñez", "Pons", "Puig", "Soler", "Mas",
})

# ── Europe (DE, FR, IT, PT, NL, PL, BE, AT) ──────────────────────────────────

EU_MALE_NAMES: frozenset[str] = frozenset({
    # German / Austrian
    "Hans", "Peter", "Klaus", "Dieter", "Werner", "Thomas", "Michael",
    "Andreas", "Stefan", "Markus", "Matthias", "Christoph", "Sebastian",
    "Tobias", "Florian", "Felix", "Lukas", "Patrick", "Tim", "Fabian",
    "Max", "Maximilian", "Johann", "Josef", "Karl", "Walter", "Otto",
    # French / Belgian
    "Jean", "Pierre", "Michel", "Philippe", "Nicolas", "François", "Luc",
    "Thierry", "Laurent", "Frédéric", "Christophe", "Guillaume", "Antoine",
    "Alexandre", "Maxime", "Baptiste", "Julien", "Romain", "Hugo", "Théo",
    "Benoît", "Sébastien", "Vincent", "Xavier", "Yannick", "Cédric",
    # Italian
    "Giovanni", "Marco", "Luca", "Francesco", "Alessandro", "Lorenzo",
    "Matteo", "Davide", "Simone", "Roberto", "Paolo", "Stefano",
    "Giuseppe", "Riccardo", "Edoardo", "Filippo", "Pietro", "Claudio",
    # Portuguese
    "João", "António", "Nuno", "Rui", "Diogo", "Tiago", "André", "Bruno",
    # Polish
    "Adam", "Andrzej", "Piotr", "Krzysztof", "Tomasz", "Michał", "Marcin",
    "Paweł", "Marek", "Łukasz", "Jakub", "Grzegorz", "Bartłomiej",
    # Dutch
    "Jan", "Pieter", "Willem", "Dirk", "Henk", "Arjan", "Ruben", "Lars",
    # Romanian
    "Mihai", "Ion", "Gheorghe", "Nicolae", "Florin", "Bogdan", "Cristian",
})

EU_FEMALE_NAMES: frozenset[str] = frozenset({
    # German / Austrian
    "Anna", "Maria", "Petra", "Ursula", "Monika", "Sabine", "Claudia",
    "Susanne", "Birgit", "Heike", "Katrin", "Julia", "Lisa", "Sophie",
    "Sarah", "Hannah", "Lena", "Emma", "Lea", "Leonie", "Katharina",
    "Franziska", "Elisabeth", "Helga", "Inge", "Hanna",
    # French / Belgian
    "Marie", "Sophie", "Camille", "Chloé", "Manon", "Léa", "Inès",
    "Lucie", "Pauline", "Amélie", "Charlotte", "Aurélie", "Nathalie",
    "Isabelle", "Véronique", "Sandrine", "Céline", "Élodie", "Virginie",
    "Martine", "Brigitte", "Sylvie", "Hélène", "Delphine",
    # Italian
    "Giulia", "Francesca", "Chiara", "Martina", "Elisa", "Valentina",
    "Federica", "Alessia", "Simona", "Paola", "Giovanna", "Roberta",
    "Silvia", "Patrizia", "Daniela", "Michela",
    # Portuguese
    "Joana", "Catarina", "Mariana", "Carolina", "Inês", "Patrícia",
    # Polish
    "Katarzyna", "Małgorzata", "Agnieszka", "Joanna", "Magdalena",
    "Monika", "Ewa", "Elżbieta", "Marta", "Beata", "Karolina",
    # Romanian
    "Elena", "Ioana", "Maria", "Ana", "Mihaela", "Andreea", "Cristina",
})

EU_SURNAMES: frozenset[str] = frozenset({
    # German
    "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner",
    "Becker", "Schulz", "Hoffmann", "Koch", "Bauer", "Richter", "Klein",
    "Wolf", "Schröder", "Neumann", "Schwarz", "Zimmermann", "Braun",
    "Krause", "Lehmann", "Lange", "Köhler", "Peters", "Maier", "Berger",
    # French
    "Martin", "Bernard", "Thomas", "Petit", "Robert", "Richard", "Durand",
    "Dubois", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel",
    "David", "Bertrand", "Roux", "Vincent", "Fournier", "Morin", "Girard",
    "Bonnet", "Dupont", "Lambert", "Fontaine", "Rousseau", "Blanc",
    # Italian
    "Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo",
    "Ricci", "Marino", "Greco", "Bruno", "Gallo", "Conti", "De Luca",
    "Mancini", "Costa", "Giordano", "Rizzo", "Lombardi", "Moretti",
    # Portuguese
    "Silva", "Santos", "Ferreira", "Pereira", "Oliveira", "Rodrigues",
    "Martins", "Sousa", "Fernandes", "Gomes", "Lopes", "Marques", "Alves",
    # Polish
    "Nowak", "Kowalski", "Wiśniewski", "Wójcik", "Kowalczyk",
    "Lewandowski", "Zielinski", "Szymanski", "Wojciechowski", "Kaczmarek",
    # Dutch
    "De Jong", "Janssen", "De Vries", "Van den Berg", "Bakker", "Visser",
    "Smit", "Meijer", "De Boer", "Mulder",
})

# ── Switzerland (BFS — multilingual: DE+FR+IT) ────────────────────────────────

CH_NAMES: frozenset[str] = frozenset({
    # German-Swiss
    "Urs", "Beat", "Heinz", "Kurt", "Walter", "Ernst", "Rudolf", "Rolf",
    "Hanspeter", "René", "Marcel", "Lukas", "Markus",
    "Yvonne", "Brigitte", "Rosmarie", "Heidi", "Vreni", "Margrit",
    "Karin", "Regula", "Doris", "Eveline", "Franziska",
    # French-Swiss
    "Jean-Pierre", "Jacques", "Henri", "Maurice", "Claude", "Yves",
    "Monique", "Françoise", "Jacqueline", "Michèle", "Sylvie",
    # Italian-Swiss
    "Paolo", "Bruno", "Giorgio", "Lucia", "Rita",
    # Common CH surnames
    "Müller", "Meier", "Keller", "Weber", "Zimmermann", "Huber", "Moser",
    "Frei", "Brunner", "Baumann", "Schneider", "Graf", "Fischer", "Gerber",
    "Lehmann", "Steiner", "Maurer", "Bucher", "Lüthi", "Etter",
})

# ── Latin America (MX, CO, AR, CL, PE, VE, EC) ───────────────────────────────

LATAM_MALE_NAMES: frozenset[str] = frozenset({
    "Alejandro", "Andrés", "Carlos", "Diego", "Eduardo", "Enrique",
    "Felipe", "Fernando", "Francisco", "Gabriel", "Gonzalo", "Guillermo",
    "Gustavo", "Hernán", "Ignacio", "Iván", "Jaime", "Javier", "Jorge",
    "José", "Juan", "Leonardo", "Luis", "Manuel", "Marcos", "Mario",
    "Miguel", "Pablo", "Pedro", "Rafael", "Ricardo", "Roberto", "Rodrigo",
    "Santiago", "Sebastián", "Sergio", "Tomás", "Víctor", "Arturo",
    "Ernesto", "Gerardo", "Héctor", "Jesús", "Ramón", "César", "Alfredo",
    "Óscar", "Mauricio", "Camilo", "Mateo", "Nicolás", "Julián",
})

LATAM_FEMALE_NAMES: frozenset[str] = frozenset({
    "Alejandra", "Ana", "Andrea", "Ángela", "Camila", "Carolina", "Claudia",
    "Daniela", "Fernanda", "Gabriela", "Isabel", "Laura", "Lucía", "Luisa",
    "Marcela", "María", "Mariana", "Natalia", "Paola", "Patricia", "Paula",
    "Rosa", "Sandra", "Sara", "Silvia", "Sofía", "Valeria", "Valentina",
    "Verónica", "Victoria", "Adriana", "Beatriz", "Catalina", "Diana",
    "Gloria", "Lorena", "Mónica", "Nadia", "Rebeca", "Viviana",
})

LATAM_SURNAMES: frozenset[str] = frozenset({
    "Acosta", "Aguilar", "Arias", "Beltrán", "Benítez", "Cabrera",
    "Cárdenas", "Castillo", "Castro", "Chávez", "Cruz", "Espinosa",
    "Flores", "Fuentes", "Gómez", "González", "Guerrero", "Gutiérrez",
    "Herrera", "Jiménez", "León", "Luna", "Medina", "Mendoza", "Molina",
    "Morales", "Muñoz", "Navarro", "Núñez", "Ortega", "Ortiz",
    "Pacheco", "Palacios", "Peña", "Pérez", "Ramos", "Reyes", "Rivera",
    "Rodríguez", "Romero", "Ruiz", "Salazar", "Sánchez", "Serrano",
    "Torres", "Vargas", "Vega", "Vásquez", "Zapata", "Rojas", "Mora",
    "Delgado", "Ávila", "Montoya", "Osorio", "Parra", "Suárez",
})

# ── USA + Canada ──────────────────────────────────────────────────────────────

US_MALE_NAMES: frozenset[str] = frozenset({
    "James", "John", "Robert", "Michael", "William", "David", "Richard",
    "Joseph", "Thomas", "Charles", "Christopher", "Daniel", "Matthew",
    "Anthony", "Donald", "Steven", "Paul", "Andrew", "Joshua", "Kenneth",
    "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward", "Jason",
    "Jeffrey", "Ryan", "Jacob", "Gary", "Nicholas", "Eric", "Jonathan",
    "Stephen", "Larry", "Justin", "Scott", "Brandon", "Benjamin", "Samuel",
    "Raymond", "Gregory", "Frank", "Alexander", "Dennis", "Jerry",
    "Nathan", "Adam", "Kyle", "Patrick", "Ethan", "Noah", "Mason",
})

US_FEMALE_NAMES: frozenset[str] = frozenset({
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth",
    "Susan", "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty",
    "Margaret", "Sandra", "Ashley", "Dorothy", "Kimberly", "Emily",
    "Donna", "Michelle", "Carol", "Amanda", "Melissa", "Deborah",
    "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia", "Kathleen",
    "Amy", "Angela", "Shirley", "Anna", "Brenda", "Pamela", "Emma",
    "Nicole", "Helen", "Samantha", "Katherine", "Christine", "Rachel",
    "Carolyn", "Janet", "Catherine", "Heather", "Amber", "Megan",
    "Hannah", "Olivia", "Abigail", "Madison", "Sophia", "Isabella",
})

US_SURNAMES: frozenset[str] = frozenset({
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Thompson", "White", "Harris", "Clark", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Hill",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Stewart", "Turner", "Phillips", "Morgan",
    "Hughes", "Cooper", "Ward", "Cox", "Howard", "Collins", "Reed",
    "Patterson", "Morgan", "Bell", "Murphy", "Bailey", "Rivera", "Price",
})

# ── United Kingdom ────────────────────────────────────────────────────────────

UK_MALE_NAMES: frozenset[str] = frozenset({
    "Oliver", "Harry", "George", "Jack", "Noah", "Charlie", "Jacob",
    "Alfie", "Freddie", "Oscar", "Arthur", "Leo", "Henry", "Archie",
    "Ethan", "Joshua", "William", "Theodore", "Stanley", "Albert",
    "Reuben", "Teddy", "Harrison", "Finley", "Alistair", "Duncan",
    # Traditional British
    "Andrew", "Richard", "Stephen", "Simon", "Ian", "Colin",
    "Nigel", "Trevor", "Clive", "Hamish", "Angus", "Malcolm",
    "Graham", "Keith", "Barry", "Derek", "Gareth", "Rhodri",
})

UK_FEMALE_NAMES: frozenset[str] = frozenset({
    "Olivia", "Amelia", "Isla", "Ava", "Mia", "Isabella", "Sophia",
    "Grace", "Lily", "Freya", "Poppy", "Rosie", "Phoebe", "Daisy",
    "Alice", "Florence", "Charlotte", "Ella", "Scarlett", "Evie",
    "Georgia", "Millie", "Ellie", "Sienna", "Isabelle", "Harriet",
    # Traditional British
    "Margaret", "Dorothy", "Edith", "Agnes", "Morag", "Fiona",
    "Eileen", "Bridget", "Claire", "Nicola", "Tracy", "Deborah",
    "Janet", "Wendy", "Shirley", "Valerie", "Brenda", "Sheila",
    "Pauline", "Yvonne", "Gwyneth", "Sioned", "Cerys",
})

UK_SURNAMES: frozenset[str] = frozenset({
    "Smith", "Jones", "Williams", "Taylor", "Brown", "Davies", "Evans",
    "Wilson", "Thomas", "Roberts", "Johnson", "Lewis", "Walker",
    "Robinson", "Wood", "Thompson", "White", "Watson", "Jackson",
    "Wright", "Green", "Harris", "Cooper", "King", "Martin", "Clarke",
    "James", "Morgan", "Hughes", "Edwards", "Hill", "Moore", "Harrison",
    "Scott", "Young", "Morris", "Hall", "Ward", "Turner", "Carter",
    "Phillips", "Mitchell", "Patel", "Adams", "Campbell", "Anderson",
    "Allen", "Cook", "Bailey", "Bell",
})

# ── Diminutivos (español) ─────────────────────────────────────────────────────

DIMINUTIVOS: frozenset[str] = frozenset({
    # User-specified
    "dani", "paco", "javi", "adri", "alex", "fer", "guille",
    "cris", "manu", "rafa", "rodri", "mari", "bea", "xavi",
    # Common additional
    "nacho", "pepe", "pepita", "loli", "conchi", "isa", "vicky",
    "santi", "toño", "toni", "nando", "fran", "quique", "kike",
    "curro", "luchi", "luci", "nati", "espe", "lola", "charo",
    "marisol", "maite", "txus", "patxi", "iker", "mikel",
})

# ── Aggregated views ──────────────────────────────────────────────────────────

ALL_FIRST_NAMES: frozenset[str] = (
    ES_MALE_NAMES | ES_FEMALE_NAMES
    | EU_MALE_NAMES | EU_FEMALE_NAMES
    | CH_NAMES
    | LATAM_MALE_NAMES | LATAM_FEMALE_NAMES
    | US_MALE_NAMES | US_FEMALE_NAMES
    | UK_MALE_NAMES | UK_FEMALE_NAMES
)

ALL_SURNAMES: frozenset[str] = (
    ES_SURNAMES
    | EU_SURNAMES
    | LATAM_SURNAMES
    | US_SURNAMES
    | UK_SURNAMES
)

# Lowercase sets for case-insensitive lookup
ALL_FIRST_NAMES_LOWER: frozenset[str] = frozenset(n.lower() for n in ALL_FIRST_NAMES)
ALL_SURNAMES_LOWER: frozenset[str] = frozenset(n.lower() for n in ALL_SURNAMES)
