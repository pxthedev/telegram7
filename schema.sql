-- Esquema gerado a partir dos modelos (python create_tables.py --sql)
-- Idempotente: pode ser executado mais de uma vez (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS products (
	id SERIAL NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	price NUMERIC(12, 2) NOT NULL, 
	stock INTEGER DEFAULT '0' NOT NULL, 
	active BOOLEAN DEFAULT 'true' NOT NULL, 
	content TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_products PRIMARY KEY (id)
)

;

CREATE INDEX IF NOT EXISTS ix_products_name ON products (name);


CREATE TABLE IF NOT EXISTS users (
	id SERIAL NOT NULL, 
	telegram_id BIGINT NOT NULL, 
	username VARCHAR(255), 
	first_name VARCHAR(255), 
	balance NUMERIC(12, 2) DEFAULT '0' NOT NULL, 
	affiliate_code VARCHAR(32), 
	referred_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_users PRIMARY KEY (id), 
	CONSTRAINT fk_users_referred_by_users FOREIGN KEY(referred_by) REFERENCES users (id) ON DELETE SET NULL
)

;

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_telegram_id ON users (telegram_id);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_affiliate_code ON users (affiliate_code);

CREATE INDEX IF NOT EXISTS ix_users_referred_by ON users (referred_by);


CREATE TABLE IF NOT EXISTS webhook_events (
	id SERIAL NOT NULL, 
	event_id VARCHAR(128) NOT NULL, 
	provider VARCHAR(32) DEFAULT 'freepay' NOT NULL, 
	payload JSON NOT NULL, 
	processed BOOLEAN DEFAULT 'false' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	processed_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_webhook_events PRIMARY KEY (id)
)

;

CREATE INDEX IF NOT EXISTS ix_webhook_events_processed ON webhook_events (processed);

CREATE UNIQUE INDEX IF NOT EXISTS ix_webhook_events_event_id ON webhook_events (event_id);


CREATE TABLE IF NOT EXISTS pix_payments (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	external_id VARCHAR(64) NOT NULL, 
	provider_payment_id VARCHAR(128), 
	amount NUMERIC(12, 2) NOT NULL, 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	qr_code TEXT, 
	pix_copy_paste TEXT, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	paid_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_pix_payments PRIMARY KEY (id), 
	CONSTRAINT fk_pix_payments_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE INDEX IF NOT EXISTS ix_pix_payments_user_id ON pix_payments (user_id);

CREATE UNIQUE INDEX IF NOT EXISTS ix_pix_payments_provider_payment_id ON pix_payments (provider_payment_id);

CREATE UNIQUE INDEX IF NOT EXISTS ix_pix_payments_external_id ON pix_payments (external_id);

CREATE INDEX IF NOT EXISTS ix_pix_payments_status ON pix_payments (status);


CREATE TABLE IF NOT EXISTS purchases (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	status VARCHAR(32) DEFAULT 'completed' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_purchases PRIMARY KEY (id), 
	CONSTRAINT uq_purchases_user_id_product_id UNIQUE (user_id, product_id), 
	CONSTRAINT fk_purchases_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_purchases_product_id_products FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT
)

;

CREATE INDEX IF NOT EXISTS ix_purchases_user_id ON purchases (user_id);

CREATE INDEX IF NOT EXISTS ix_purchases_product_id ON purchases (product_id);


CREATE TABLE IF NOT EXISTS transactions (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	type VARCHAR(32) NOT NULL, 
	description TEXT, 
	reference_id VARCHAR(128), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_transactions PRIMARY KEY (id), 
	CONSTRAINT fk_transactions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE INDEX IF NOT EXISTS ix_transactions_type ON transactions (type);

CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_deposit_ref ON transactions (type, reference_id) WHERE type = 'DEPOSIT' AND reference_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_transactions_user_created ON transactions (user_id, created_at);

CREATE INDEX IF NOT EXISTS ix_transactions_user_id ON transactions (user_id);


CREATE TABLE IF NOT EXISTS affiliates (
	id SERIAL NOT NULL, 
	affiliate_id INTEGER NOT NULL, 
	referred_id INTEGER NOT NULL, 
	purchase_id INTEGER NOT NULL, 
	commission NUMERIC(12, 2) NOT NULL, 
	status VARCHAR(32) DEFAULT 'paid' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_affiliates PRIMARY KEY (id), 
	CONSTRAINT uq_affiliates_purchase_id UNIQUE (purchase_id), 
	CONSTRAINT fk_affiliates_affiliate_id_users FOREIGN KEY(affiliate_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_affiliates_referred_id_users FOREIGN KEY(referred_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_affiliates_purchase_id_purchases FOREIGN KEY(purchase_id) REFERENCES purchases (id) ON DELETE CASCADE
)

;

CREATE INDEX IF NOT EXISTS ix_affiliates_referred_id ON affiliates (referred_id);

CREATE INDEX IF NOT EXISTS ix_affiliates_affiliate_id ON affiliates (affiliate_id);


-- =====================================================================
-- ALTERAÇÕES PARA BANCO EXISTENTE
-- Cadastro de cliente desativado: remove as colunas de cadastro.
-- Seguro de rodar quantas vezes for preciso (IF EXISTS).
-- =====================================================================

ALTER TABLE users DROP COLUMN IF EXISTS customer_name;
ALTER TABLE users DROP COLUMN IF EXISTS customer_email;
ALTER TABLE users DROP COLUMN IF EXISTS customer_phone;
ALTER TABLE users DROP COLUMN IF EXISTS customer_document_type;
ALTER TABLE users DROP COLUMN IF EXISTS customer_document_number;


-- =====================================================================
-- ROW LEVEL SECURITY nas tabelas do schema public
-- (o bot usa a conexão direta via asyncpg, que ignora RLS)
-- =====================================================================

ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE pix_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchases ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE affiliates ENABLE ROW LEVEL SECURITY;
