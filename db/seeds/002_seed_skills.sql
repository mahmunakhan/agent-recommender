-- ============================================================================
-- SKILL TAXONOMY SEED DATA
-- ============================================================================

USE job_recommendation;

-- ============================================================================
-- LEVEL 0: ROOT CATEGORIES (8 categories)
-- ============================================================================
INSERT INTO skill_categories (id, name, slug, parent_id, description, level, path, display_order) VALUES
('cat-tech', 'Technology', 'technology', NULL, 'Technical and engineering skills', 0, '/technology', 1),
('cat-data', 'Data & Analytics', 'data-analytics', NULL, 'Data science and analytics', 0, '/data-analytics', 2),
('cat-ai', 'AI & Machine Learning', 'ai-ml', NULL, 'Artificial intelligence and ML', 0, '/ai-ml', 3),
('cat-cloud', 'Cloud & DevOps', 'cloud-devops', NULL, 'Cloud platforms and DevOps', 0, '/cloud-devops', 4),
('cat-business', 'Business', 'business', NULL, 'Business and management skills', 0, '/business', 5),
('cat-soft', 'Soft Skills', 'soft-skills', NULL, 'Interpersonal and soft skills', 0, '/soft-skills', 6),
('cat-design', 'Design', 'design', NULL, 'UI/UX and visual design', 0, '/design', 7),
('cat-lang', 'Languages', 'languages', NULL, 'Human languages', 0, '/languages', 8);

-- ============================================================================
-- LEVEL 1: SUB-CATEGORIES
-- ============================================================================
INSERT INTO skill_categories (id, name, slug, parent_id, description, level, path, display_order) VALUES
-- Technology subcategories
('cat-prog-lang', 'Programming Languages', 'programming-languages', 'cat-tech', 'Programming and scripting languages', 1, '/technology/programming-languages', 1),
('cat-frameworks', 'Frameworks & Libraries', 'frameworks-libraries', 'cat-tech', 'Development frameworks', 1, '/technology/frameworks-libraries', 2),
('cat-databases', 'Databases', 'databases', 'cat-tech', 'Database technologies', 1, '/technology/databases', 3),
('cat-api', 'APIs & Web Services', 'apis-web-services', 'cat-tech', 'API development', 1, '/technology/apis-web-services', 4),

-- Data subcategories
('cat-data-eng', 'Data Engineering', 'data-engineering', 'cat-data', 'Data pipelines and engineering', 1, '/data-analytics/data-engineering', 1),
('cat-data-viz', 'Data Visualization', 'data-visualization', 'cat-data', 'BI and visualization tools', 1, '/data-analytics/data-visualization', 2),
('cat-data-analysis', 'Data Analysis', 'data-analysis', 'cat-data', 'Statistical analysis', 1, '/data-analytics/data-analysis', 3),

-- AI/ML subcategories
('cat-ml', 'Machine Learning', 'machine-learning', 'cat-ai', 'ML algorithms and techniques', 1, '/ai-ml/machine-learning', 1),
('cat-dl', 'Deep Learning', 'deep-learning', 'cat-ai', 'Neural networks and DL', 1, '/ai-ml/deep-learning', 2),
('cat-nlp', 'NLP', 'nlp', 'cat-ai', 'Natural language processing', 1, '/ai-ml/nlp', 3),
('cat-cv', 'Computer Vision', 'computer-vision', 'cat-ai', 'Image and video processing', 1, '/ai-ml/computer-vision', 4),
('cat-genai', 'Generative AI', 'generative-ai', 'cat-ai', 'LLMs and generative models', 1, '/ai-ml/generative-ai', 5),
('cat-mlops', 'MLOps', 'mlops', 'cat-ai', 'ML operations and deployment', 1, '/ai-ml/mlops', 6),

-- Cloud subcategories
('cat-cloud-plat', 'Cloud Platforms', 'cloud-platforms', 'cat-cloud', 'Major cloud providers', 1, '/cloud-devops/cloud-platforms', 1),
('cat-containers', 'Containers & Orchestration', 'containers', 'cat-cloud', 'Docker, Kubernetes', 1, '/cloud-devops/containers', 2),
('cat-cicd', 'CI/CD', 'cicd', 'cat-cloud', 'Continuous integration/deployment', 1, '/cloud-devops/cicd', 3),
('cat-infra', 'Infrastructure as Code', 'infrastructure-as-code', 'cat-cloud', 'Terraform, Ansible', 1, '/cloud-devops/infrastructure-as-code', 4),

-- Business subcategories
('cat-pm', 'Project Management', 'project-management', 'cat-business', 'Project and product management', 1, '/business/project-management', 1),
('cat-agile', 'Agile & Scrum', 'agile-scrum', 'cat-business', 'Agile methodologies', 1, '/business/agile-scrum', 2);

-- ============================================================================
-- SKILLS: PROGRAMMING LANGUAGES
-- ============================================================================
INSERT INTO skills (id, name, slug, category_id, skill_type, is_verified, popularity_score, description) VALUES
('skill-python', 'Python', 'python', 'cat-prog-lang', 'technical', TRUE, 95, 'General-purpose programming language'),
('skill-javascript', 'JavaScript', 'javascript', 'cat-prog-lang', 'technical', TRUE, 92, 'Web programming language'),
('skill-typescript', 'TypeScript', 'typescript', 'cat-prog-lang', 'technical', TRUE, 85, 'Typed superset of JavaScript'),
('skill-java', 'Java', 'java', 'cat-prog-lang', 'technical', TRUE, 88, 'Enterprise programming language'),
('skill-csharp', 'C#', 'csharp', 'cat-prog-lang', 'technical', TRUE, 80, 'Microsoft .NET language'),
('skill-cpp', 'C++', 'cpp', 'cat-prog-lang', 'technical', TRUE, 75, 'Systems programming language'),
('skill-go', 'Go', 'go', 'cat-prog-lang', 'technical', TRUE, 78, 'Google systems language'),
('skill-rust', 'Rust', 'rust', 'cat-prog-lang', 'technical', TRUE, 70, 'Memory-safe systems language'),
('skill-sql', 'SQL', 'sql', 'cat-prog-lang', 'technical', TRUE, 90, 'Database query language'),
('skill-r', 'R', 'r', 'cat-prog-lang', 'technical', TRUE, 65, 'Statistical programming'),
('skill-scala', 'Scala', 'scala', 'cat-prog-lang', 'technical', TRUE, 55, 'JVM functional language'),
('skill-kotlin', 'Kotlin', 'kotlin', 'cat-prog-lang', 'technical', TRUE, 60, 'Modern JVM language'),
('skill-swift', 'Swift', 'swift', 'cat-prog-lang', 'technical', TRUE, 58, 'Apple development language'),
('skill-php', 'PHP', 'php', 'cat-prog-lang', 'technical', TRUE, 60, 'Web scripting language'),
('skill-ruby', 'Ruby', 'ruby', 'cat-prog-lang', 'technical', TRUE, 50, 'Dynamic programming language'),
('skill-bash', 'Bash', 'bash', 'cat-prog-lang', 'technical', TRUE, 70, 'Shell scripting');

-- ============================================================================
-- SKILLS: FRAMEWORKS & LIBRARIES
-- ============================================================================
INSERT INTO skills (id, name, slug, category_id, skill_type, is_verified, popularity_score, description) VALUES
('skill-react', 'React', 'react', 'cat-frameworks', 'technical', TRUE, 90, 'JavaScript UI library'),
('skill-angular', 'Angular', 'angular', 'cat-frameworks', 'technical', TRUE, 75, 'TypeScript web framework'),
('skill-vue', 'Vue.js', 'vuejs', 'cat-frameworks', 'technical', TRUE, 70, 'Progressive JS framework'),
('skill-nextjs', 'Next.js', 'nextjs', 'cat-frameworks', 'technical', TRUE, 80, 'React framework'),
('skill-nodejs', 'Node.js', 'nodejs', 'cat-frameworks', 'technical', TRUE, 88, 'JavaScript runtime'),
('skill-express', 'Express.js', 'expressjs', 'cat-frameworks', 'technical', TRUE, 75, 'Node.js web framework'),
('skill-django', 'Django', 'django', 'cat-frameworks', 'technical', TRUE, 72, 'Python web framework'),
('skill-flask', 'Flask', 'flask', 'cat-frameworks', 'technical', TRUE, 68, 'Python micro framework'),
('skill-fastapi', 'FastAPI', 'fastapi', 'cat-frameworks', 'technical', TRUE, 78, 'Modern Python API framework'),
('skill-spring', 'Spring Boot', 'spring-boot', 'cat-frameworks', 'technical', TRUE, 80, 'Java enterprise framework'),
('skill-dotnet', '.NET Core', 'dotnet-core', 'cat-frameworks', 'technical', TRUE, 75, 'Microsoft framework'),
('skill-rails', 'Ruby on Rails', 'ruby-on-rails', 'cat-frameworks', 'technical', TRUE, 55, 'Ruby web framework');

-- ============================================================================
-- SKILLS: DATABASES
-- ============================================================================
INSERT INTO skills (id, name, slug, category_id, skill_type, is_verified, popularity_score, description) VALUES
('skill-postgresql', 'PostgreSQL', 'postgresql', 'cat-databases', 'technical', TRUE, 88, 'Advanced relational database'),
('skill-mysql', 'MySQL', 'mysql', 'cat-databases', 'technical', TRUE, 85, 'Popular relational database'),
('skill-mongodb', 'MongoDB', 'mongodb', 'cat-databases', 'technical', TRUE, 78, 'Document database'),
('skill-redis', 'Redis', 'redis', 'cat-databases', 'technical', TRUE, 75, 'In-memory data store'),
('skill-elasticsearch', 'Elasticsearch', 'elasticsearch', 'cat-databases', 'technical', TRUE, 70, 'Search and analytics engine'),
('skill-cassandra', 'Cassandra', 'cassandra', 'cat-databases', 'technical', TRUE, 55, 'Distributed database'),
('skill-dynamodb', 'DynamoDB', 'dynamodb', 'cat-databases', 'technical', TRUE, 65, 'AWS NoSQL database'),
('skill-neo4j', 'Neo4j', 'neo4j', 'cat-databases', 'technical', TRUE, 50, 'Graph database'),
('skill-snowflake', 'Snowflake', 'snowflake', 'cat-databases', 'technical', TRUE, 72, 'Cloud data warehouse'),
('skill-bigquery', 'BigQuery', 'bigquery', 'cat-databases', 'technical', TRUE, 70, 'Google data warehouse');

-- ============================================================================
-- SKILLS: AI & MACHINE LEARNING
-- ============================================================================
INSERT INTO skills (id, name, slug, category_id, skill_type, is_verified, popularity_score, description) VALUES
('skill-ml', 'Machine Learning', 'machine-learning', 'cat-ml', 'technical', TRUE, 92, 'ML algorithms and models'),
('skill-dl', 'Deep Learning', 'deep-learning', 'cat-dl', 'technical', TRUE, 88, 'Neural network techniques'),
('skill-tensorflow', 'TensorFlow', 'tensorflow', 'cat-dl', 'tool', TRUE, 85, 'Google ML framework'),
('skill-pytorch', 'PyTorch', 'pytorch', 'cat-dl', 'tool', TRUE, 88, 'Facebook ML framework'),
('skill-keras', 'Keras', 'keras', 'cat-dl', 'tool', TRUE, 75, 'High-level neural networks API'),
('skill-sklearn', 'scikit-learn', 'scikit-learn', 'cat-ml', 'tool', TRUE, 85, 'Python ML library'),
('skill-xgboost', 'XGBoost', 'xgboost', 'cat-ml', 'tool', TRUE, 75, 'Gradient boosting library'),
('skill-lightgbm', 'LightGBM', 'lightgbm', 'cat-ml', 'tool', TRUE, 65, 'Fast gradient boosting'),
('skill-nlp', 'Natural Language Processing', 'nlp', 'cat-nlp', 'technical', TRUE, 82, 'Text and language AI'),
('skill-cv', 'Computer Vision', 'computer-vision', 'cat-cv', 'technical', TRUE, 78, 'Image and video AI'),
('skill-opencv', 'OpenCV', 'opencv', 'cat-cv', 'tool', TRUE, 70, 'Computer vision library'),
('skill-transformers', 'Transformers', 'transformers', 'cat-dl', 'technical', TRUE, 85, 'Attention-based models'),
('skill-huggingface', 'Hugging Face', 'hugging-face', 'cat-genai', 'tool', TRUE, 82, 'ML model hub and library'),
('skill-langchain', 'LangChain', 'langchain', 'cat-genai', 'tool', TRUE, 80, 'LLM application framework'),
('skill-langgraph', 'LangGraph', 'langgraph', 'cat-genai', 'tool', TRUE, 70, 'LLM workflow framework'),
('skill-llamaindex', 'LlamaIndex', 'llamaindex', 'cat-genai', 'tool', TRUE, 68, 'LLM data framework'),
('skill-openai-api', 'OpenAI API', 'openai-api', 'cat-genai', 'tool', TRUE, 85, 'OpenAI services'),
('skill-llm', 'Large Language Models', 'llm', 'cat-genai', 'technical', TRUE, 88, 'LLM development'),
('skill-rag', 'RAG', 'rag', 'cat-genai', 'technical', TRUE, 78, 'Retrieval Augmented Generation'),
('skill-prompt-eng', 'Prompt Engineering', 'prompt-engineering', 'cat-genai', 'technical', TRUE, 75, 'LLM prompt design'),
('skill-genai', 'Generative AI', 'generative-ai', 'cat-genai', 'technical', TRUE, 85, 'Generative models'),
('skill-ai-agents', 'AI Agents', 'ai-agents', 'cat-genai', 'technical', TRUE, 72, 'Autonomous AI systems');

-- ============================================================================
-- SKILLS: DATA ENGINEERING
-- ============================================================================
INSERT INTO skills (id, name, slug, category_id, skill_type, is_verified, popularity_score, description) VALUES
('skill-pandas', 'Pandas', 'pandas', 'cat-data-eng', 'tool', TRUE, 90, 'Python data manipulation'),
('skill-numpy', 'NumPy', 'numpy', 'cat-data-eng', 'tool', TRUE, 88, 'Python numerical computing'),
('skill-spark', 'Apache Spark', 'apache-spark', 'cat-data-eng', 'tool', TRUE, 82, 'Big data processing'),
('skill-pyspark', 'PySpark', 'pyspark', 'cat-data-eng', 'tool', TRUE, 78, 'Spark Python API'),
('skill-kafka', 'Apache Kafka', 'apache-kafka', 'cat-data-eng', 'tool', TRUE, 75, 'Event streaming platform'),
('skill-airflow', 'Apache Airflow', 'apache-airflow', 'cat-data-eng', 'tool', TRUE, 78, 'Workflow orchestration'),
('skill-dbt', 'dbt', 'dbt', 'cat-data-eng', 'tool', TRUE, 72, 'Data transformation tool'),
('skill-etl', 'ETL', 'etl', 'cat-data-eng', 'technical', TRUE, 80, 'Extract-Transform-Load'),
('skill-data-pipeline', 'Data Pipelines', 'data-pipelines', 'cat-data-eng', 'technical', TRUE, 78, 'Pipeline design');

-- ============================================================================
-- SKILLS: DATA VISUALIZATION
-- ============================================================================
INSERT INTO skills (id, name, slug, category_id, skill_type, is_verified, popularity_score, description) VALUES
('skill-tableau', 'Tableau', 'tableau', 'cat-data-viz', 'tool', TRUE, 80, 'BI visualization tool'),
('skill-powerbi', 'Power BI', 'power-bi', 'cat-data-viz', 'tool', TRUE, 82, 'Microsoft BI tool'),
('skill-matplotlib', 'Matplotlib', 'matplotlib', 'cat-data-viz', 'tool', TRUE, 75, 'Python plotting library'),
('skill-plotly', 'Plotly', 'plotly', 'cat-data-viz', 'tool', TRUE, 70, 'Interactive visualization'),
('skill-grafana', 'Grafana', 'grafana', 'cat-data-viz', 'tool', TRUE, 68, 'Metrics visualization');

-- ============================================================================
-- SKILLS: CLOUD PLATFORMS
-- ============================================================================
INSERT INTO skills (id, name, slug, category_id, skill_type, is_verified, popularity_score, description) VALUES
('skill-aws', 'AWS', 'aws', 'cat-cloud-plat', 'technical', TRUE, 92, 'Amazon Web Services'),
('skill-azure', 'Azure', 'azure', 'cat-cloud-plat', 'technical', TRUE, 85, 'Microsoft Cloud'),
('skill-gcp', 'Google Cloud', 'gcp', 'cat-cloud-plat', 'technical', TRUE, 80, 'Google Cloud Platform'),
('skill-sagemaker', 'SageMaker', 'sagemaker', 'cat-cloud-plat', 'tool', TRUE, 70, 'AWS ML service'),
('skill-bedrock', 'AWS Bedrock', 'aws-bedrock', 'cat-cloud-plat', 'tool', TRUE, 65, 'AWS GenAI service'),
('skill-vertex-ai', 'Vertex AI', 'vertex-ai', 'cat-cloud-plat', 'tool', TRUE, 68, 'Google ML platform');

-- ============================================================================
-- SKILLS: CONTAINERS & DEVOPS
-- ============================================================================
INSERT INTO skills (id, name, slug, category_id, skill_type, is_verified, popularity_score, description) VALUES
('skill-docker', 'Docker', 'docker', 'cat-containers', 'tool', TRUE, 90, 'Container platform'),
('skill-kubernetes', 'Kubernetes', 'kubernetes', 'cat-containers', 'tool', TRUE, 85, 'Container orchestration'),
('skill-helm', 'Helm', 'helm', 'cat-containers', 'tool', TRUE, 65, 'Kubernetes package manager'),
('skill-terraform', 'Terraform', 'terraform', 'cat-infra', 'tool', TRUE, 80, 'Infrastructure as code'),
('skill-ansible', 'Ansible', 'ansible', 'cat-infra', 'tool', TRUE, 70, 'Configuration management'),
('skill-jenkins', 'Jenkins', 'jenkins', 'cat-cicd', 'tool', TRUE, 72, 'CI/CD automation'),
('skill-github-actions', 'GitHub Actions', 'github-actions', 'cat-cicd', 'tool', TRUE, 78, 'GitHub CI/CD'),
('skill-gitlab-ci', 'GitLab CI', 'gitlab-ci', 'cat-cicd', 'tool', TRUE, 70, 'GitLab CI/CD'),
('skill-cicd', 'CI/CD', 'cicd', 'cat-cicd', 'technical', TRUE, 82, 'Continuous integration/deployment'),
('skill-mlops', 'MLOps', 'mlops', 'cat-mlops', 'technical', TRUE, 78, 'ML operations'),
('skill-mlflow', 'MLflow', 'mlflow', 'cat-mlops', 'tool', TRUE, 70, 'ML lifecycle management');

-- ============================================================================
-- SKILLS: VECTOR DATABASES
-- ============================================================================
INSERT INTO skills (id, name, slug, category_id, skill_type, is_verified, popularity_score, description) VALUES
('skill-pinecone', 'Pinecone', 'pinecone', 'cat-databases', 'tool', TRUE, 70, 'Vector database'),
('skill-weaviate', 'Weaviate', 'weaviate', 'cat-databases', 'tool', TRUE, 62, 'Vector search engine'),
('skill-milvus', 'Milvus', 'milvus', 'cat-databases', 'tool', TRUE, 65, 'Vector database'),
('skill-chroma', 'ChromaDB', 'chromadb', 'cat-databases', 'tool', TRUE, 60, 'Embedding database'),
('skill-pgvector', 'pgvector', 'pgvector', 'cat-databases', 'tool', TRUE, 58, 'PostgreSQL vectors'),
('skill-qdrant', 'Qdrant', 'qdrant', 'cat-databases', 'tool', TRUE, 55, 'Vector search engine'),
('skill-faiss', 'FAISS', 'faiss', 'cat-databases', 'tool', TRUE, 68, 'Facebook similarity search');

-- ============================================================================
-- SKILLS: APIs
-- ============================================================================
INSERT INTO skills (id, name, slug, category_id, skill_type, is_verified, popularity_score, description) VALUES
('skill-rest-api', 'REST API', 'rest-api', 'cat-api', 'technical', TRUE, 88, 'RESTful web services'),
('skill-graphql', 'GraphQL', 'graphql', 'cat-api', 'technical', TRUE, 70, 'Query language for APIs'),
('skill-grpc', 'gRPC', 'grpc', 'cat-api', 'technical', TRUE, 60, 'High-performance RPC'),
('skill-websocket', 'WebSocket', 'websocket', 'cat-api', 'technical', TRUE, 65, 'Real-time communication');

-- ============================================================================
-- SKILLS: SOFT SKILLS
-- ============================================================================
INSERT INTO skills (id, name, slug, category_id, skill_type, is_verified, popularity_score, description) VALUES
('skill-communication', 'Communication', 'communication', 'cat-soft', 'soft', TRUE, 90, 'Verbal and written communication'),
('skill-teamwork', 'Teamwork', 'teamwork', 'cat-soft', 'soft', TRUE, 88, 'Collaboration skills'),
('skill-leadership', 'Leadership', 'leadership', 'cat-soft', 'soft', TRUE, 85, 'Leading teams'),
('skill-problem-solving', 'Problem Solving', 'problem-solving', 'cat-soft', 'soft', TRUE, 90, 'Analytical thinking'),
('skill-time-mgmt', 'Time Management', 'time-management', 'cat-soft', 'soft', TRUE, 80, 'Managing priorities'),
('skill-presentation', 'Presentation', 'presentation', 'cat-soft', 'soft', TRUE, 75, 'Public speaking');

-- ============================================================================
-- SKILLS: PROJECT MANAGEMENT
-- ============================================================================
INSERT INTO skills (id, name, slug, category_id, skill_type, is_verified, popularity_score, description) VALUES
('skill-agile', 'Agile', 'agile', 'cat-agile', 'domain', TRUE, 85, 'Agile methodology'),
('skill-scrum', 'Scrum', 'scrum', 'cat-agile', 'domain', TRUE, 82, 'Scrum framework'),
('skill-kanban', 'Kanban', 'kanban', 'cat-agile', 'domain', TRUE, 70, 'Kanban methodology'),
('skill-jira', 'Jira', 'jira', 'cat-pm', 'tool', TRUE, 80, 'Project tracking tool'),
('skill-confluence', 'Confluence', 'confluence', 'cat-pm', 'tool', TRUE, 65, 'Documentation tool');

-- ============================================================================
-- SKILL ALIASES
-- ============================================================================
INSERT INTO skill_aliases (skill_id, alias, alias_type, is_preferred) VALUES
('skill-python', 'Python3', 'version', FALSE),
('skill-python', 'py', 'abbreviation', FALSE),
('skill-javascript', 'JS', 'abbreviation', TRUE),
('skill-javascript', 'ECMAScript', 'alternate', FALSE),
('skill-typescript', 'TS', 'abbreviation', TRUE),
('skill-csharp', 'C Sharp', 'alternate', FALSE),
('skill-cpp', 'C Plus Plus', 'alternate', FALSE),
('skill-go', 'Golang', 'alternate', TRUE),
('skill-postgresql', 'Postgres', 'abbreviation', TRUE),
('skill-postgresql', 'PgSQL', 'abbreviation', FALSE),
('skill-kubernetes', 'K8s', 'abbreviation', TRUE),
('skill-kubernetes', 'Kube', 'abbreviation', FALSE),
('skill-ml', 'ML', 'abbreviation', TRUE),
('skill-dl', 'DL', 'abbreviation', TRUE),
('skill-nlp', 'Natural Language Processing', 'alternate', FALSE),
('skill-cv', 'CV', 'abbreviation', TRUE),
('skill-sklearn', 'sklearn', 'abbreviation', TRUE),
('skill-aws', 'Amazon Web Services', 'alternate', FALSE),
('skill-gcp', 'GCP', 'abbreviation', TRUE),
('skill-gcp', 'Google Cloud Platform', 'alternate', FALSE),
('skill-llm', 'LLMs', 'alternate', FALSE),
('skill-llm', 'Large Language Model', 'alternate', FALSE),
('skill-genai', 'GenAI', 'abbreviation', TRUE),
('skill-cicd', 'CI CD', 'alternate', FALSE),
('skill-cicd', 'CICD', 'alternate', FALSE),
('skill-langchain', 'Lang Chain', 'alternate', FALSE),
('skill-langgraph', 'Lang Graph', 'alternate', FALSE),
('skill-rag', 'Retrieval Augmented Generation', 'alternate', FALSE),
('skill-huggingface', 'HuggingFace', 'alternate', FALSE),
('skill-huggingface', 'HF', 'abbreviation', FALSE),
('skill-fastapi', 'Fast API', 'alternate', FALSE),
('skill-pyspark', 'Py Spark', 'alternate', FALSE),
('skill-powerbi', 'PowerBI', 'alternate', FALSE),
('skill-mlops', 'ML Ops', 'alternate', FALSE);

-- ============================================================================
-- LEARNING PROVIDERS
-- ============================================================================
INSERT INTO learning_providers (id, name, slug, website_url, provider_type, quality_score, has_certificates, has_free_content) VALUES
('prov-coursera', 'Coursera', 'coursera', 'https://www.coursera.org', 'mooc', 85, TRUE, TRUE),
('prov-udemy', 'Udemy', 'udemy', 'https://www.udemy.com', 'mooc', 70, TRUE, FALSE),
('prov-deeplearning', 'DeepLearning.AI', 'deeplearning-ai', 'https://www.deeplearning.ai', 'mooc', 95, TRUE, FALSE),
('prov-pluralsight', 'Pluralsight', 'pluralsight', 'https://www.pluralsight.com', 'video', 80, TRUE, FALSE),
('prov-youtube', 'YouTube', 'youtube', 'https://www.youtube.com', 'video', 60, FALSE, TRUE),
('prov-aws-training', 'AWS Training', 'aws-training', 'https://aws.amazon.com/training', 'certification', 90, TRUE, TRUE),
('prov-google-cloud', 'Google Cloud Training', 'google-cloud-training', 'https://cloud.google.com/training', 'certification', 88, TRUE, TRUE),
('prov-microsoft-learn', 'Microsoft Learn', 'microsoft-learn', 'https://learn.microsoft.com', 'certification', 85, TRUE, TRUE),
('prov-datacamp', 'DataCamp', 'datacamp', 'https://www.datacamp.com', 'mooc', 75, TRUE, FALSE),
('prov-udacity', 'Udacity', 'udacity', 'https://www.udacity.com', 'mooc', 82, TRUE, FALSE);

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================
SELECT 
    (SELECT COUNT(*) FROM skill_categories) as categories,
    (SELECT COUNT(*) FROM skills) as skills,
    (SELECT COUNT(*) FROM skill_aliases) as aliases,
    (SELECT COUNT(*) FROM learning_providers) as providers;