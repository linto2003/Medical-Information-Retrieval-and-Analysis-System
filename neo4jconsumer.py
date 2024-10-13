from confluent_kafka import Consumer, KafkaError
from neo4j import GraphDatabase
import json

uri="URL OF YOUR NEO4j",
username="YOUR USER NAME",
password="YOUR PASSWORD"

driver = GraphDatabase.driver(uri, auth=(username, password))

def create_medicine(tx, name, uses, side_effects, composition):
    query = (
        "MERGE (m:Medicine {name: $name}) "
        "WITH m "
        "UNWIND $uses AS use "
        "MERGE (u:Use {description: use}) "
        "MERGE (m)-[:HAS_USE]->(u) "
        "WITH m "
        "UNWIND $side_effects AS side_effect "
        "MERGE (s:SideEffect {description: side_effect}) "
        "MERGE (m)-[:HAS_SIDE_EFFECT]->(s) "
        "WITH m "
        "UNWIND $composition AS comp "
        "MERGE (c:Composition {description: comp}) "
        "MERGE (m)-[:HAS_COMPOSITION]->(c)"
    )
    tx.run(query, name=name, uses=uses, side_effects=side_effects, composition=composition)

def consume_and_store():
  
    consumer_conf = {
        'bootstrap.servers': 'localhost:8097', 
        'group.id': 'my-consumer-group',
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': True,
    }

    consumer = Consumer(consumer_conf)
    consumer.subscribe(['randomTopic'])  

    try:
        while True:
            msg = consumer.poll(1.0)  

            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    
                    continue
                else:
                    print(f"Error: {msg.error()}")
                    break

            
            data = json.loads(msg.value().decode('utf-8'))
           
            name = data.get("name")
            uses = data.get("uses", [])
            side_effects = data.get("side effects", [])
            composition = data.get("composition", [])

            with driver.session() as session:
                session.execute_write(create_medicine, name, uses, side_effects, composition)

            print(f"Stored medicine: {name}")

    finally:
        consumer.close()

consume_and_store()

driver.close()
