import datetime
from app.core.database import SessionLocal, engine
from app.models.models import WeatherObservation
from sqlalchemy import text

RAW_DATA = """102	Anantapur	32.2	52	2026-10-15 06:00:00+00:00
120	Gangtok	22.5	43	2026-10-15 06:00:00+00:00
119	Itanagar	29	48	2026-10-15 06:00:00+00:00
118	Kohima	23.4	50	2026-10-15 06:00:00+00:00
117	Aizawl	25.7	59	2026-10-15 06:00:00+00:00
116	Imphal	27.2	57	2026-10-15 06:00:00+00:00
115	Margao	35.5	37	2026-10-15 06:00:00+00:00
114	Panaji	35.3	37	2026-10-15 06:00:00+00:00
113	Asansol	30.9	58	2026-10-15 06:00:00+00:00
112	Durgapur	31.4	56	2026-10-15 06:00:00+00:00
111	Rourkela	31.3	58	2026-10-15 06:00:00+00:00
110	Sambalpur	30	70	2026-10-15 06:00:00+00:00
109	Rewa	29.3	54	2026-10-15 06:00:00+00:00
108	Satna	29.9	49	2026-10-15 06:00:00+00:00
107	Sagar	28.9	44	2026-10-15 06:00:00+00:00
106	Khammam	33	53	2026-10-15 06:00:00+00:00
105	Nizamabad	31.4	44	2026-10-15 06:00:00+00:00
104	Karimnagar	31.1	56	2026-10-15 06:00:00+00:00
103	Kurnool	34	40	2026-10-15 06:00:00+00:00
76	Ajmer	33.1	33	2026-10-15 05:45:00+00:00
60	Srinagar	14.6	63	2026-10-15 05:45:00+00:00
61	Jammu	21.8	69	2026-10-15 05:45:00+00:00
62	Agra	31.8	42	2026-10-15 05:45:00+00:00
63	Varanasi	30.2	57	2026-10-15 05:45:00+00:00
64	Prayagraj	29.9	56	2026-10-15 05:45:00+00:00
65	Kanpur	31	46	2026-10-15 05:45:00+00:00
66	Meerut	23.9	83	2026-10-15 05:45:00+00:00
67	Gwalior	30.8	45	2026-10-15 05:45:00+00:00
68	Jabalpur	29.5	51	2026-10-15 05:45:00+00:00
69	Cuttack	28.2	81	2026-10-15 05:45:00+00:00
70	Bhubaneswar	28.6	77	2026-10-15 05:45:00+00:00
71	Siliguri	29.7	60	2026-10-15 05:45:00+00:00
72	Dhanbad	30.7	51	2026-10-15 05:45:00+00:00
73	Jamshedpur	30.8	59	2026-10-15 05:45:00+00:00
74	Bikaner	33.5	37	2026-10-15 05:45:00+00:00
75	Kota	32.8	38	2026-10-15 05:45:00+00:00
77	Bareilly	28.8	60	2026-10-15 05:45:00+00:00
78	Moradabad	20.6	95	2026-10-15 05:45:00+00:00
79	Aligarh	28.3	56	2026-10-15 05:45:00+00:00
80	Guntur	32.5	59	2026-10-15 05:45:00+00:00
81	Nellore	30.7	69	2026-10-15 05:45:00+00:00
82	Anantapur	31.9	53	2026-10-15 05:45:00+00:00
83	Kurnool	33.7	41	2026-10-15 05:45:00+00:00
84	Karimnagar	30.8	57	2026-10-15 05:45:00+00:00
85	Nizamabad	31.1	45	2026-10-15 05:45:00+00:00
86	Khammam	32.8	54	2026-10-15 05:45:00+00:00
87	Sagar	28.7	45	2026-10-15 05:45:00+00:00
88	Satna	29.7	50	2026-10-15 05:45:00+00:00
89	Rewa	29.1	55	2026-10-15 05:45:00+00:00
90	Sambalpur	29.9	70	2026-10-15 05:45:00+00:00
91	Rourkela	31.1	59	2026-10-15 05:45:00+00:00
92	Anantapur	31.9	53	2026-10-15 05:45:00+00:00
93	Kurnool	33.7	41	2026-10-15 05:45:00+00:00
94	Karimnagar	30.8	57	2026-10-15 05:45:00+00:00
95	Nizamabad	31.1	45	2026-10-15 05:45:00+00:00
96	Khammam	32.8	54	2026-10-15 05:45:00+00:00
97	Sagar	28.7	45	2026-10-15 05:45:00+00:00
98	Satna	29.7	50	2026-10-15 05:45:00+00:00
99	Rewa	29.1	55	2026-10-15 05:45:00+00:00
100	Sambalpur	29.9	70	2026-10-15 05:45:00+00:00
101	Rourkela	31.1	59	2026-10-15 05:45:00+00:00
42	Jaipur	31.6	41	2026-10-15 05:45:00+00:00
43	Kolkata	33.1	53	2026-10-15 05:45:00+00:00
44	Lucknow	29.9	55	2026-10-15 05:45:00+00:00
45	Bhopal	30.3	38	2026-10-15 05:45:00+00:00
46	Patna	30.8	56	2026-10-15 05:45:00+00:00
47	Guwahati	31.2	54	2026-10-15 05:45:00+00:00
48	Shimla	15	54	2026-10-15 05:45:00+00:00
49	Dehradun	22.8	83	2026-10-15 05:45:00+00:00
50	Amritsar	28.4	53	2026-10-15 05:45:00+00:00
51	Nagpur	31.4	44	2026-10-15 05:45:00+00:00
52	Ranchi	26.6	71	2026-10-15 05:45:00+00:00
53	Raipur	30	59	2026-10-15 05:45:00+00:00
54	Thiruvananthapuram	29	77	2026-10-15 05:45:00+00:00
55	Vijayapura	31.4	36	2026-10-15 05:45:00+00:00
56	Hubballi	32	39	2026-10-15 05:45:00+00:00
57	Warangal	31.5	54	2026-10-15 05:45:00+00:00
58	Jodhpur	36.1	25	2026-10-15 05:45:00+00:00
59	Udaipur	32.5	35	2026-10-15 05:45:00+00:00
21	Delhi	23.7	87	2026-10-15 05:30:00+00:00
22	Tirunelveli	32	60	2026-10-15 05:30:00+00:00
23	Thanjavur	30.6	68	2026-10-15 05:30:00+00:00
24	Vellore	26.3	88	2026-10-15 05:30:00+00:00
25	Tiruppur	32.3	51	2026-10-15 05:30:00+00:00
26	Erode	32.8	48	2026-10-15 05:30:00+00:00
27	Chennai	29.1	77	2026-10-15 05:30:00+00:00
28	Coimbatore	33.7	40	2026-10-15 05:30:00+00:00
29	Madurai	29.5	70	2026-10-15 05:30:00+00:00
30	Salem	30.4	64	2026-10-15 05:30:00+00:00
31	Bengaluru	29.5	46	2026-10-15 05:30:00+00:00
32	Puducherry	27.4	87	2026-10-15 05:30:00+00:00
33	Kochi	29.5	75	2026-10-15 05:30:00+00:00
34	Mysuru	30.9	42	2026-10-15 05:30:00+00:00
35	Vijayawada	32.2	59	2026-10-15 05:30:00+00:00
36	Visakhapatnam	30.2	69	2026-10-15 05:30:00+00:00
37	Mangaluru	31.8	60	2026-10-15 05:30:00+00:00
38	Tirupati	28.6	78	2026-10-15 05:30:00+00:00
39	Kozhikode	30.7	68	2026-10-15 05:30:00+00:00
40	Kanyakumari	28.2	79	2026-10-15 05:30:00+00:00
41	Ooty	17	82	2026-10-15 05:30:00+00:00
2	Erode	32.8	48	2026-10-15 05:30:00+00:00
20	Mumbai	35.7	29	2026-10-15 05:30:00+00:00
19	Hyderabad	30.9	46	2026-10-15 05:30:00+00:00
18	Bengaluru	29.5	46	2026-10-15 05:30:00+00:00
17	Tiruchirappalli	31.6	62	2026-10-15 05:30:00+00:00
16	Salem	30.4	64	2026-10-15 05:30:00+00:00
15	Madurai	29.5	70	2026-10-15 05:30:00+00:00
14	Coimbatore	33.7	40	2026-10-15 05:30:00+00:00
13	Chennai	29.1	77	2026-10-15 05:30:00+00:00
12	Erode	32.8	48	2026-10-15 05:30:00+00:00
11	Delhi	23.7	87	2026-10-15 05:30:00+00:00
10	Mumbai	35.7	29	2026-10-15 05:30:00+00:00
9	Hyderabad	30.9	46	2026-10-15 05:30:00+00:00
8	Bengaluru	29.5	46	2026-10-15 05:30:00+00:00
1	Erode	32.8	48	2026-10-15 05:30:00+00:00
7	Tiruchirappalli	31.6	62	2026-10-15 05:30:00+00:00
6	Salem	30.4	64	2026-10-15 05:30:00+00:00
5	Madurai	29.5	70	2026-10-15 05:30:00+00:00
4	Coimbatore	33.7	40	2026-10-15 05:30:00+00:00
3	Chennai	29.1	77	2026-10-15 05:30:00+00:00"""

def main():
    db = SessionLocal()
    lines = [l.strip() for l in RAW_DATA.strip().split("\n") if l.strip()]
    print(f"Total raw lines: {len(lines)}")
    
    inserted_count = 0
    now = datetime.datetime.utcnow()
    
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        
        _, location, temp_str, hum_str, time_str = parts[0], parts[1], parts[2], parts[3], parts[4]
        try:
            temp = float(temp_str)
            hum = float(hum_str)
            clean_time_str = time_str.replace("+00:00", "").replace("Z", "")
            obs_time = datetime.datetime.fromisoformat(clean_time_str)
        except Exception as e:
            print(f"Error parsing line: {line} -> {e}")
            continue

        # Prevent exact duplicates (location + observation_time)
        existing = db.query(WeatherObservation).filter(
            WeatherObservation.location_name == location,
            WeatherObservation.observation_time == obs_time
        ).first()

        if not existing:
            obs = WeatherObservation(
                location_name=location,
                latitude=15.0,
                longitude=78.0,
                temperature=temp,
                relative_humidity=hum,
                wind_speed=8.5,
                weather_code=1 if hum < 60 else 3,
                surface_pressure=1012.0,
                precipitation=0.0,
                cloud_cover=min(hum, 100.0),
                observation_time=obs_time,
                api_fetched_at=now,
                database_inserted_at=now
            )
            db.add(obs)
            inserted_count += 1

    db.commit()
    total_in_db = db.query(WeatherObservation).count()
    db.close()
    
    print(f"Successfully inserted {inserted_count} new records into AWS RDS PostgreSQL!")
    print(f"Total records now in AWS RDS: {total_in_db}")

if __name__ == "__main__":
    main()
