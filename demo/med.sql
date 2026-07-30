--
-- PostgreSQL database dump
--
-- DEMO-ONLY DATASET for PatientMonitor local/demo installs.
-- Do not import clinical/production patient data into this dump.
-- Doctor passwords below are deliberately non-production demo values.
--

-- Dumped from database version 15.2
-- Dumped by pg_dump version 15.2

-- Started on 2025-05-15 13:30:06

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 241 (class 1259 OID 16845)
-- Name: alarm_param; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alarm_param (
    alarm_id integer NOT NULL,
    alarm_name character varying(28),
    alarm_descr_rus character varying(64),
    alarm_descr_eng character varying(64)
);


ALTER TABLE public.alarm_param OWNER TO postgres;

--
-- TOC entry 240 (class 1259 OID 16844)
-- Name: alarm_param_alarm_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.alarm_param_alarm_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.alarm_param_alarm_id_seq OWNER TO postgres;

--
-- TOC entry 3573 (class 0 OID 0)
-- Dependencies: 240
-- Name: alarm_param_alarm_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.alarm_param_alarm_id_seq OWNED BY public.alarm_param.alarm_id;


--
-- TOC entry 243 (class 1259 OID 16852)
-- Name: alarms; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alarms (
    alarms_id integer NOT NULL,
    bed_id integer NOT NULL,
    alarm_id integer NOT NULL,
    alarm_date_time timestamp without time zone,
    alarm_message character varying(64),
    alarm_status integer DEFAULT 1 NOT NULL
);


ALTER TABLE public.alarms OWNER TO postgres;

--
-- TOC entry 242 (class 1259 OID 16851)
-- Name: alarms_alarms_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.alarms_alarms_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.alarms_alarms_id_seq OWNER TO postgres;

--
-- TOC entry 3574 (class 0 OID 0)
-- Dependencies: 242
-- Name: alarms_alarms_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.alarms_alarms_id_seq OWNED BY public.alarms.alarms_id;


--
-- TOC entry 229 (class 1259 OID 16727)
-- Name: bed; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bed (
    bed_id integer NOT NULL,
    bed_numb integer NOT NULL,
    bed_name character varying(64),
    block_id integer NOT NULL,
    room_id integer NOT NULL,
    status_id integer NOT NULL,
    patient_id integer DEFAULT 0
);


ALTER TABLE public.bed OWNER TO postgres;

--
-- TOC entry 228 (class 1259 OID 16726)
-- Name: bed_bed_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.bed_bed_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.bed_bed_id_seq OWNER TO postgres;

--
-- TOC entry 3575 (class 0 OID 0)
-- Dependencies: 228
-- Name: bed_bed_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.bed_bed_id_seq OWNED BY public.bed.bed_id;


--
-- TOC entry 225 (class 1259 OID 16709)
-- Name: block; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.block (
    block_id integer NOT NULL,
    block_numb character varying(16) NOT NULL,
    block_name character varying(64)
);


ALTER TABLE public.block OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 16708)
-- Name: block_block_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.block_block_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.block_block_id_seq OWNER TO postgres;

--
-- TOC entry 3576 (class 0 OID 0)
-- Dependencies: 224
-- Name: block_block_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.block_block_id_seq OWNED BY public.block.block_id;


--
-- TOC entry 239 (class 1259 OID 16838)
-- Name: color; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.color (
    color_id integer NOT NULL,
    color_name character varying(28),
    color_name_rus character varying(64)
);


ALTER TABLE public.color OWNER TO postgres;

--
-- TOC entry 238 (class 1259 OID 16837)
-- Name: color_color_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.color_color_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.color_color_id_seq OWNER TO postgres;

--
-- TOC entry 3577 (class 0 OID 0)
-- Dependencies: 238
-- Name: color_color_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.color_color_id_seq OWNED BY public.color.color_id;


--
-- TOC entry 221 (class 1259 OID 16681)
-- Name: doctor; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.doctor (
    doctor_id integer NOT NULL,
    doctor_numb character varying(15) NOT NULL,
    doctor_name character varying(64),
    spec_id integer NOT NULL,
    status_id integer NOT NULL,
    doctor_password character varying(15) NOT NULL,
    doctor_login character varying(15) NOT NULL
);


ALTER TABLE public.doctor OWNER TO postgres;

--
-- TOC entry 220 (class 1259 OID 16680)
-- Name: doctor_doctor_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.doctor_doctor_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.doctor_doctor_id_seq OWNER TO postgres;

--
-- TOC entry 3578 (class 0 OID 0)
-- Dependencies: 220
-- Name: doctor_doctor_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.doctor_doctor_id_seq OWNED BY public.doctor.doctor_id;


--
-- TOC entry 249 (class 1259 OID 16922)
-- Name: grup; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.grup (
    group_id integer NOT NULL,
    group_numb character varying(16) NOT NULL,
    group_name character varying(64),
    group_descr_rus character varying(64)
);


ALTER TABLE public.grup OWNER TO postgres;

--
-- TOC entry 248 (class 1259 OID 16921)
-- Name: grup_group_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.grup_group_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.grup_group_id_seq OWNER TO postgres;

--
-- TOC entry 3579 (class 0 OID 0)
-- Dependencies: 248
-- Name: grup_group_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.grup_group_id_seq OWNED BY public.grup.group_id;


--
-- TOC entry 247 (class 1259 OID 16893)
-- Name: images; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.images (
    images_id integer NOT NULL,
    bed_id integer NOT NULL,
    images_date_time timestamp without time zone,
    image bytea
);


ALTER TABLE public.images OWNER TO postgres;

--
-- TOC entry 246 (class 1259 OID 16892)
-- Name: images_images_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.images_images_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.images_images_id_seq OWNER TO postgres;

--
-- TOC entry 3580 (class 0 OID 0)
-- Dependencies: 246
-- Name: images_images_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.images_images_id_seq OWNED BY public.images.images_id;


--
-- TOC entry 253 (class 1259 OID 78709)
-- Name: list; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.list (
    list_id integer NOT NULL,
    list_numb character varying(16),
    list_name character varying(54)
);


ALTER TABLE public.list OWNER TO postgres;

--
-- TOC entry 252 (class 1259 OID 78708)
-- Name: list_list_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.list_list_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.list_list_id_seq OWNER TO postgres;

--
-- TOC entry 3581 (class 0 OID 0)
-- Dependencies: 252
-- Name: list_list_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.list_list_id_seq OWNED BY public.list.list_id;


--
-- TOC entry 255 (class 1259 OID 415970)
-- Name: mode_app; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mode_app (
    mode_app_id integer NOT NULL,
    mode_app_numb character varying(64) NOT NULL,
    mode_app_name character varying(64),
    mode_app_status integer NOT NULL
);


ALTER TABLE public.mode_app OWNER TO postgres;

--
-- TOC entry 254 (class 1259 OID 415968)
-- Name: mode_app_mode_app_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.mode_app_mode_app_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.mode_app_mode_app_id_seq OWNER TO postgres;

--
-- TOC entry 3582 (class 0 OID 0)
-- Dependencies: 254
-- Name: mode_app_mode_app_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.mode_app_mode_app_id_seq OWNED BY public.mode_app.mode_app_id;


--
-- TOC entry 215 (class 1259 OID 16654)
-- Name: patient; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.patient (
    patient_id integer NOT NULL,
    patient_numb character varying(64) NOT NULL,
    patient_name character varying(64),
    patient_birth_date date,
    patient_sex character(2),
    patient_address character varying(64),
    patient_telephone_number_1 character(12),
    patient_telephone_number_2 character(12)
);


ALTER TABLE public.patient OWNER TO postgres;

--
-- TOC entry 214 (class 1259 OID 16653)
-- Name: patient_patient_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.patient_patient_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.patient_patient_id_seq OWNER TO postgres;

--
-- TOC entry 3583 (class 0 OID 0)
-- Dependencies: 214
-- Name: patient_patient_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.patient_patient_id_seq OWNED BY public.patient.patient_id;


--
-- TOC entry 223 (class 1259 OID 16700)
-- Name: room; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.room (
    room_id integer NOT NULL,
    room_numb character varying(16) NOT NULL,
    room_name character varying(64),
    block_id integer,
    php_session character varying(64) DEFAULT 'unknown'::character varying NOT NULL,
    doctor_id integer,
    date_time timestamp without time zone,
    mode_app_id integer
);


ALTER TABLE public.room OWNER TO postgres;

--
-- TOC entry 222 (class 1259 OID 16699)
-- Name: room_room_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.room_room_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.room_room_id_seq OWNER TO postgres;

--
-- TOC entry 3584 (class 0 OID 0)
-- Dependencies: 222
-- Name: room_room_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.room_room_id_seq OWNED BY public.room.room_id;


--
-- TOC entry 251 (class 1259 OID 16931)
-- Name: signal_param; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.signal_param (
    signal_id integer NOT NULL,
    group_id integer NOT NULL,
    signal_name character varying(64),
    signal_descr_rus character varying(64),
    signal_descr_eng character varying(64),
    signal_unit character varying(12),
    signal_min real,
    signal_max real,
    status_param integer DEFAULT 0
);


ALTER TABLE public.signal_param OWNER TO postgres;

--
-- TOC entry 250 (class 1259 OID 16930)
-- Name: signal_param_signal_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.signal_param_signal_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.signal_param_signal_id_seq OWNER TO postgres;

--
-- TOC entry 3585 (class 0 OID 0)
-- Dependencies: 250
-- Name: signal_param_signal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.signal_param_signal_id_seq OWNED BY public.signal_param.signal_id;


--
-- TOC entry 237 (class 1259 OID 16821)
-- Name: signals; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.signals (
    signals_id integer NOT NULL,
    bed_id integer NOT NULL,
    signal_id integer NOT NULL,
    signals_date_time timestamp without time zone,
    signals_value real
);


ALTER TABLE public.signals OWNER TO postgres;

--
-- TOC entry 236 (class 1259 OID 16820)
-- Name: signals_signals_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.signals_signals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.signals_signals_id_seq OWNER TO postgres;

--
-- TOC entry 3586 (class 0 OID 0)
-- Dependencies: 236
-- Name: signals_signals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.signals_signals_id_seq OWNED BY public.signals.signals_id;


--
-- TOC entry 217 (class 1259 OID 16663)
-- Name: spec; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.spec (
    spec_id integer NOT NULL,
    spec_numb character varying(64) NOT NULL,
    spec_name character varying(64)
);


ALTER TABLE public.spec OWNER TO postgres;

--
-- TOC entry 216 (class 1259 OID 16662)
-- Name: spec_spec_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.spec_spec_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.spec_spec_id_seq OWNER TO postgres;

--
-- TOC entry 3587 (class 0 OID 0)
-- Dependencies: 216
-- Name: spec_spec_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.spec_spec_id_seq OWNED BY public.spec.spec_id;


--
-- TOC entry 219 (class 1259 OID 16672)
-- Name: status; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.status (
    status_id integer NOT NULL,
    status_numb character varying(64) NOT NULL,
    status_name character varying(64)
);


ALTER TABLE public.status OWNER TO postgres;

--
-- TOC entry 227 (class 1259 OID 16718)
-- Name: status_bed; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.status_bed (
    status_id integer NOT NULL,
    status_numb integer NOT NULL,
    status_name character varying(64)
);


ALTER TABLE public.status_bed OWNER TO postgres;

--
-- TOC entry 226 (class 1259 OID 16717)
-- Name: status_bed_status_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.status_bed_status_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.status_bed_status_id_seq OWNER TO postgres;

--
-- TOC entry 3588 (class 0 OID 0)
-- Dependencies: 226
-- Name: status_bed_status_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.status_bed_status_id_seq OWNED BY public.status_bed.status_id;


--
-- TOC entry 218 (class 1259 OID 16671)
-- Name: status_status_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.status_status_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.status_status_id_seq OWNER TO postgres;

--
-- TOC entry 3589 (class 0 OID 0)
-- Dependencies: 218
-- Name: status_status_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.status_status_id_seq OWNED BY public.status.status_id;


--
-- TOC entry 235 (class 1259 OID 16805)
-- Name: storage; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.storage (
    storage_id integer NOT NULL,
    storage_numb character varying(16),
    storage_path character varying(2048),
    description character varying(256)
);


ALTER TABLE public.storage OWNER TO postgres;

--
-- TOC entry 234 (class 1259 OID 16804)
-- Name: storage_storage_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.storage_storage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.storage_storage_id_seq OWNER TO postgres;

--
-- TOC entry 3590 (class 0 OID 0)
-- Dependencies: 234
-- Name: storage_storage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.storage_storage_id_seq OWNED BY public.storage.storage_id;


--
-- TOC entry 231 (class 1259 OID 16752)
-- Name: study; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.study (
    study_id integer NOT NULL,
    study_numb character varying(16),
    patient_id integer NOT NULL,
    doctor_id integer NOT NULL,
    bed_id integer NOT NULL,
    date_beg date,
    date_end date,
    time_beg time without time zone,
    time_end time without time zone,
    study_descr character varying(256),
    study_text character varying(50000)
);


ALTER TABLE public.study OWNER TO postgres;

--
-- TOC entry 230 (class 1259 OID 16751)
-- Name: study_study_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.study_study_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.study_study_id_seq OWNER TO postgres;

--
-- TOC entry 3591 (class 0 OID 0)
-- Dependencies: 230
-- Name: study_study_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.study_study_id_seq OWNED BY public.study.study_id;


--
-- TOC entry 245 (class 1259 OID 16870)
-- Name: videos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.videos (
    videos_id integer NOT NULL,
    storage_id integer NOT NULL,
    bed_id integer NOT NULL,
    doctor_id integer NOT NULL,
    videos_date_time_beg timestamp without time zone,
    videos_date_time_end timestamp without time zone,
    video_cnt integer DEFAULT 0 NOT NULL,
    video_comments character varying(64)
);


ALTER TABLE public.videos OWNER TO postgres;

--
-- TOC entry 244 (class 1259 OID 16869)
-- Name: videos_videos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.videos_videos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.videos_videos_id_seq OWNER TO postgres;

--
-- TOC entry 3592 (class 0 OID 0)
-- Dependencies: 244
-- Name: videos_videos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.videos_videos_id_seq OWNED BY public.videos.videos_id;


--
-- TOC entry 233 (class 1259 OID 16776)
-- Name: worklist; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.worklist (
    worklist_id integer NOT NULL,
    worklist_numb character varying(10),
    patient_id integer NOT NULL,
    doctor_id integer NOT NULL,
    room_id integer NOT NULL,
    block_id integer NOT NULL,
    date_beg date,
    date_end date,
    time_beg time without time zone,
    time_end time without time zone,
    worklist_descr character varying(256),
    worklist_text character varying(50000)
);


ALTER TABLE public.worklist OWNER TO postgres;

--
-- TOC entry 232 (class 1259 OID 16775)
-- Name: worklist_worklist_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.worklist_worklist_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.worklist_worklist_id_seq OWNER TO postgres;

--
-- TOC entry 3593 (class 0 OID 0)
-- Dependencies: 232
-- Name: worklist_worklist_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.worklist_worklist_id_seq OWNED BY public.worklist.worklist_id;


--
-- TOC entry 3288 (class 2604 OID 16848)
-- Name: alarm_param alarm_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alarm_param ALTER COLUMN alarm_id SET DEFAULT nextval('public.alarm_param_alarm_id_seq'::regclass);


--
-- TOC entry 3289 (class 2604 OID 16855)
-- Name: alarms alarms_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alarms ALTER COLUMN alarms_id SET DEFAULT nextval('public.alarms_alarms_id_seq'::regclass);


--
-- TOC entry 3281 (class 2604 OID 16730)
-- Name: bed bed_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bed ALTER COLUMN bed_id SET DEFAULT nextval('public.bed_bed_id_seq'::regclass);


--
-- TOC entry 3279 (class 2604 OID 16712)
-- Name: block block_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.block ALTER COLUMN block_id SET DEFAULT nextval('public.block_block_id_seq'::regclass);


--
-- TOC entry 3287 (class 2604 OID 16841)
-- Name: color color_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.color ALTER COLUMN color_id SET DEFAULT nextval('public.color_color_id_seq'::regclass);


--
-- TOC entry 3276 (class 2604 OID 16684)
-- Name: doctor doctor_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.doctor ALTER COLUMN doctor_id SET DEFAULT nextval('public.doctor_doctor_id_seq'::regclass);


--
-- TOC entry 3294 (class 2604 OID 16925)
-- Name: grup group_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grup ALTER COLUMN group_id SET DEFAULT nextval('public.grup_group_id_seq'::regclass);


--
-- TOC entry 3293 (class 2604 OID 16896)
-- Name: images images_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.images ALTER COLUMN images_id SET DEFAULT nextval('public.images_images_id_seq'::regclass);


--
-- TOC entry 3297 (class 2604 OID 78712)
-- Name: list list_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.list ALTER COLUMN list_id SET DEFAULT nextval('public.list_list_id_seq'::regclass);


--
-- TOC entry 3298 (class 2604 OID 415973)
-- Name: mode_app mode_app_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mode_app ALTER COLUMN mode_app_id SET DEFAULT nextval('public.mode_app_mode_app_id_seq'::regclass);


--
-- TOC entry 3273 (class 2604 OID 16657)
-- Name: patient patient_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.patient ALTER COLUMN patient_id SET DEFAULT nextval('public.patient_patient_id_seq'::regclass);


--
-- TOC entry 3277 (class 2604 OID 16703)
-- Name: room room_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.room ALTER COLUMN room_id SET DEFAULT nextval('public.room_room_id_seq'::regclass);


--
-- TOC entry 3295 (class 2604 OID 16934)
-- Name: signal_param signal_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.signal_param ALTER COLUMN signal_id SET DEFAULT nextval('public.signal_param_signal_id_seq'::regclass);


--
-- TOC entry 3286 (class 2604 OID 16824)
-- Name: signals signals_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.signals ALTER COLUMN signals_id SET DEFAULT nextval('public.signals_signals_id_seq'::regclass);


--
-- TOC entry 3274 (class 2604 OID 16666)
-- Name: spec spec_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.spec ALTER COLUMN spec_id SET DEFAULT nextval('public.spec_spec_id_seq'::regclass);


--
-- TOC entry 3275 (class 2604 OID 16675)
-- Name: status status_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.status ALTER COLUMN status_id SET DEFAULT nextval('public.status_status_id_seq'::regclass);


--
-- TOC entry 3280 (class 2604 OID 16721)
-- Name: status_bed status_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.status_bed ALTER COLUMN status_id SET DEFAULT nextval('public.status_bed_status_id_seq'::regclass);


--
-- TOC entry 3285 (class 2604 OID 16808)
-- Name: storage storage_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.storage ALTER COLUMN storage_id SET DEFAULT nextval('public.storage_storage_id_seq'::regclass);


--
-- TOC entry 3283 (class 2604 OID 16755)
-- Name: study study_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.study ALTER COLUMN study_id SET DEFAULT nextval('public.study_study_id_seq'::regclass);


--
-- TOC entry 3291 (class 2604 OID 16873)
-- Name: videos videos_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.videos ALTER COLUMN videos_id SET DEFAULT nextval('public.videos_videos_id_seq'::regclass);


--
-- TOC entry 3284 (class 2604 OID 16779)
-- Name: worklist worklist_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.worklist ALTER COLUMN worklist_id SET DEFAULT nextval('public.worklist_worklist_id_seq'::regclass);


--
-- TOC entry 3553 (class 0 OID 16845)
-- Dependencies: 241
-- Data for Name: alarm_param; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.alarm_param (alarm_id, alarm_name, alarm_descr_rus, alarm_descr_eng) FROM stdin;
1	alarm_1	Тревога номер 1	ALARM #1
2	alarm_2	Тревога номер 2	ALARM #2
3	alarm_3	Тревога номер 3	ALARM #3
4	alarm_4	Тревога номер 4	ALARM #4
5	alarm_5	Тревога номер 5	ALARM #5
6	alarm_6	Тревога номер 6	ALARM #6
7	alarm_7	Тревога номер 7	ALARM #7
8	alarm_8	Тревога номер 8	ALARM #8
9	alarm_9	Тревога номер 9	ALARM #9
10	alarm_10	Тревога номер 10	ALARM #10
\.


--
-- TOC entry 3555 (class 0 OID 16852)
-- Dependencies: 243
-- Data for Name: alarms; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.alarms (alarms_id, bed_id, alarm_id, alarm_date_time, alarm_message, alarm_status) FROM stdin;
\.


--
-- TOC entry 3541 (class 0 OID 16727)
-- Dependencies: 229
-- Data for Name: bed; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.bed (bed_id, bed_numb, bed_name, block_id, room_id, status_id, patient_id) FROM stdin;
10	10	Койко-место № 10	2	4	1	0
6	6	Койко-место № 6	4	3	1	0
7	7	Койко-место № 7	3	3	1	0
8	8	Койко-место № 8	3	4	1	0
9	9	Койко-место № 9	2	4	1	0
4	4	Койко-место № 4	4	2	1	0
2	2	Койко-место № 2	4	1	2	13
1	1	Койко-место № 1	4	1	2	1
5	5	Койко-место № 5	4	2	1	0
3	3	Койко-место № 3	4	1	1	0
\.


--
-- TOC entry 3537 (class 0 OID 16709)
-- Dependencies: 225
-- Data for Name: block; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.block (block_id, block_numb, block_name) FROM stdin;
2	1	Нейрохирургическое-1
3	2	Нейрохирургическое-2
4	3	ОАиР-1
5	4	ОАиР-2
\.


--
-- TOC entry 3551 (class 0 OID 16838)
-- Dependencies: 239
-- Data for Name: color; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.color (color_id, color_name, color_name_rus) FROM stdin;
1	red	Красный
2	orange	Оранжевый
3	yellow	Желтый
4	blue	Синий
5	aqua	Голубой
6	green	Зеленый
7	lime	Травяной
8	white	Белый
9	SlateBlue	Сиреневый
\.


--
-- TOC entry 3533 (class 0 OID 16681)
-- Dependencies: 221
-- Data for Name: doctor; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.doctor (doctor_id, doctor_numb, doctor_name, spec_id, status_id, doctor_password, doctor_login) FROM stdin;
1	---	Не выбрано	1	1	demo_none	---
2	001	Иванов	3	2	demo_pass_11	101
3	002	Петров	2	2	demo_pass_22	102
4	003	Семенов	3	2	demo_pass_33	103
5	004	Федоров	4	2	demo_pass_44	104
6	005	Лекарев	5	2	demo_pass_55	105
7	006	Провизоров	6	1	demo_pass_66	106
8	007	Фармацевтов	7	2	demo_pass_77	107
9	9876543210	Без Фамилии	2	4	demo_0000	0000
\.


--
-- TOC entry 3561 (class 0 OID 16922)
-- Dependencies: 249
-- Data for Name: grup; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.grup (group_id, group_numb, group_name, group_descr_rus) FROM stdin;
2	2	TEMP	Температура2
1	1	HEMD	Давление1
3	3	RESP	Пульс3
4	4	POXM	Газы
5	5	CONC	Газы
7	7	ECGR	кардиограмма
6	6	ANST	Анестезия
\.


--
-- TOC entry 3559 (class 0 OID 16893)
-- Dependencies: 247
-- Data for Name: images; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.images (images_id, bed_id, images_date_time, image) FROM stdin;
\.


--
-- TOC entry 3565 (class 0 OID 78709)
-- Dependencies: 253
-- Data for Name: list; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.list (list_id, list_numb, list_name) FROM stdin;
1	1	Параметры
2	2	Цвета
\.


--
-- TOC entry 3567 (class 0 OID 415970)
-- Dependencies: 255
-- Data for Name: mode_app; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.mode_app (mode_app_id, mode_app_numb, mode_app_name, mode_app_status) FROM stdin;
1	01	Ординаторская	1
2	02	Пост медсестры	2
\.


--
-- TOC entry 3527 (class 0 OID 16654)
-- Dependencies: 215
-- Data for Name: patient; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.patient (patient_id, patient_numb, patient_name, patient_birth_date, patient_sex, patient_address, patient_telephone_number_1, patient_telephone_number_2) FROM stdin;
1	0001	Пациент-1	1925-09-25	м 	ул. Строителей, 9	+7916121516 	+7917124589 
2	0002	Пациент-2	1978-01-20	м 	ул. Мелиоративная, 25	+7925121170 	+7925124515 
3	0003	Пациент-3	2000-01-17	ж 	ул. Балтийская, 15	+7916178516 	+7917124458 
4	0004	Пациент-4	1989-01-31	м 	ул. Атлантическая, 19	+793712145  	+7968178989 
5	0005	Пациент-5	1993-07-02	ж 	ул. Абрикосовая, 175	+7918125916 	+7915124459 
6	0006	Пациент-6	1963-04-15	м 	ул. Каштановая, 12	+7916124523 	+7915121245 
7	0007	Пациент-7	1979-11-02	м 	ул. Сливовая, 125	+7925121478 	+7926124156 
8	0008	Пациент-8	1955-08-19	ж 	ул. Энтузиастов, 45	+7916121125 	+7917124325 
9	0009	Пациент-9	1995-03-14	м 	ул. Центральная, 29	+7945121516 	+7948124589 
10	0010	Пациент-10	1990-06-21	м 	ул. Лесистая, 10	+7978121516 	+7989124589 
11	0011	Пациент-11	1985-07-28	ж 	ул. Камышовая, 205	+7978121516 	+7989124589 
12	0012	Пациент-12	1974-02-17	м 	ул. Ромашковая, 17	+7978121516 	+7989124589 
14	1237	Пациент-13	2000-01-17	ж 	ул. Балтийская, 15	+7916178516 	+7917124458 
15	1238	Пациент-13	1989-01-31	м 	ул. Атлантическая, 19	+793712145  	+7968178989 
16	1239	Пациент-13	1993-07-02	ж 	ул. Абрикосовая, 175	+7918125916 	+7915124459 
17	1240	Пациент-13	1963-04-15	м 	ул. Каштановая, 12	+7916124523 	+7915121245 
18	1241	Пациент-13	1993-07-02	м 	ул. Сливовая, 125	+7925121478 	+7926124156 
19	1242	Пациент-13	1955-08-19	ж 	ул. Энтузиастов, 45	+7916121125 	+7917124325 
20	1243	Пациент-13	1995-03-14	м 	ул. Центральная, 29	+7945121516 	+7948124589 
21	1244	Пациент-13	1990-06-21	м 	ул. Лесистая, 10	+7978121516 	+7989124589 
22	1245	Пациент-13	1989-01-31	м 	ул. Атлантическая, 19	+793712145  	+7968178989 
23	1246	Пациент-13	1993-07-02	ж 	ул. Абрикосовая, 175	+7918125916 	+7915124459 
24	1247	Пациент-13	1993-07-02	м 	ул. Каштановая, 12	+7916124523 	+7915121245 
25	1248	Пациент-13	1979-11-02	м 	ул. Сливовая, 125	+7925121478 	+7926124156 
26	1249	Пациент-13	1955-08-19	ж 	ул. Энтузиастов, 45	+7916121125 	+7917124325 
27	1250	Пациент-13	1995-03-14	м 	ул. Центральная, 29	+7945121516 	+7948124589 
28	1251	Пациент-13	1990-06-21	м 	ул. Лесистая, 10	+7978121516 	+7989124589 
29	1252	Пациент-13	1925-09-25	м 	ул. Строителей, 9	+7916121516 	+7917124589 
30	1253	Пациент-13	1978-01-20	м 	ул. Мелиоративная, 25	+7925121170 	+7925124515 
31	1254	Пациент-13	2000-01-17	ж 	ул. Балтийская, 15	+7916178516 	+7917124458 
32	1255	Пациент-13	1989-01-31	м 	ул. Атлантическая, 19	+793712145  	+7968178989 
33	1256	Пациент-13	1993-07-02	ж 	ул. Абрикосовая, 175	+7918125916 	+7915124459 
34	1257	Пациент-13	1963-04-15	м 	ул. Каштановая, 12	+7916124523 	+7915121245 
35	1258	Пациент-13	1979-11-02	м 	ул. Сливовая, 125	+7925121478 	+7926124156 
36	1259	Пациент-13	1955-08-19	ж 	ул. Энтузиастов, 45	+7916121125 	+7917124325 
37	1260	Пациент-13	1995-03-14	м 	ул. Центральная, 29	+7945121516 	+7948124589 
38	1291	Пациент-13	1925-09-25	м 	ул. Строителей, 9	+7916121516 	+7917124589 
39	1292	Пациент-13	1978-01-20	м 	ул. Мелиоративная, 25	+7925121170 	+7925124515 
40	1293	Пациент-13	2000-01-17	ж 	ул. Балтийская, 15	+7916178516 	+7917124458 
41	1294	Пациент-13	1989-01-31	м 	ул. Атлантическая, 19	+793712145  	+7968178989 
42	1295	Пациент-13	1993-07-02	ж 	ул. Абрикосовая, 175	+7918125916 	+7915124459 
43	1296	Пациент-13	1963-04-15	м 	ул. Каштановая, 12	+7916124523 	+7915121245 
44	1297	Пациент-13	1993-07-02	м 	ул. Сливовая, 125	+7925121478 	+7926124156 
45	1298	Пациент-13	1955-08-19	ж 	ул. Энтузиастов, 45	+7916121125 	+7917124325 
46	1299	Пациент-13	1995-03-14	м 	ул. Центральная, 29	+7945121516 	+7948124589 
47	1300	Пациент-13	1990-06-21	м 	ул. Лесистая, 10	+7978121516 	+7989124589 
48	1301	Пациент-13	1989-01-31	м 	ул. Атлантическая, 19	+793712145  	+7968178989 
49	1302	Пациент-13	1993-07-02	ж 	ул. Абрикосовая, 175	+7918125916 	+7915124459 
50	1303	Пациент-13	1993-07-02	м 	ул. Каштановая, 12	+7916124523 	+7915121245 
51	1304	Пациент-13	1979-11-02	м 	ул. Сливовая, 125	+7925121478 	+7926124156 
52	1305	Пациент-13	1955-08-19	ж 	ул. Энтузиастов, 45	+7916121125 	+7917124325 
53	1306	Пациент-13	1995-03-14	м 	ул. Центральная, 29	+7945121516 	+7948124589 
54	1307	Пациент-13	1990-06-21	м 	ул. Лесистая, 10	+7978121516 	+7989124589 
55	1308	Пациент-13	1925-09-25	м 	ул. Строителей, 9	+7916121516 	+7917124589 
56	1309	Пациент-13	1978-01-20	м 	ул. Мелиоративная, 25	+7925121170 	+7925124515 
57	1310	Пациент-13	2000-01-17	ж 	ул. Балтийская, 15	+7916178516 	+7917124458 
58	1311	Пациент-13	1989-01-31	м 	ул. Атлантическая, 19	+793712145  	+7968178989 
59	1312	Пациент-13	1993-07-02	ж 	ул. Абрикосовая, 175	+7918125916 	+7915124459 
60	1313	Пациент-13	1963-04-15	м 	ул. Каштановая, 12	+7916124523 	+7915121245 
61	1314	Пациент-13	1979-11-02	м 	ул. Сливовая, 125	+7925121478 	+7926124156 
62	1315	Пациент-13	1955-08-19	ж 	ул. Энтузиастов, 45	+7916121125 	+7917124325 
63	1316	Пациент-13	1995-03-14	м 	ул. Центральная, 29	+7945121516 	+7948124589 
64	1347	Пациент-13	1925-09-25	м 	ул. Строителей, 9	+7916121516 	+7917124589 
65	1348	Пациент-13	1978-01-20	м 	ул. Мелиоративная, 25	+7925121170 	+7925124515 
66	1349	Пациент-13	2000-01-17	ж 	ул. Балтийская, 15	+7916178516 	+7917124458 
67	1350	Пациент-13	1989-01-31	м 	ул. Атлантическая, 19	+793712145  	+7968178989 
68	1351	Пациент-13	1993-07-02	ж 	ул. Абрикосовая, 175	+7918125916 	+7915124459 
69	1352	Пациент-13	1963-04-15	м 	ул. Каштановая, 12	+7916124523 	+7915121245 
70	1353	Пациент-13	1993-07-02	м 	ул. Сливовая, 125	+7925121478 	+7926124156 
71	1354	Пациент-13	1955-08-19	ж 	ул. Энтузиастов, 45	+7916121125 	+7917124325 
72	1355	Пациент-13	1995-03-14	м 	ул. Центральная, 29	+7945121516 	+7948124589 
73	1356	Пациент-13	1990-06-21	м 	ул. Лесистая, 10	+7978121516 	+7989124589 
74	1357	Пациент-13	1989-01-31	м 	ул. Атлантическая, 19	+793712145  	+7968178989 
75	1358	Пациент-13	1993-07-02	ж 	ул. Абрикосовая, 175	+7918125916 	+7915124459 
76	1359	Пациент-13	1993-07-02	м 	ул. Каштановая, 12	+7916124523 	+7915121245 
77	1360	Пациент-13	1979-11-02	м 	ул. Сливовая, 125	+7925121478 	+7926124156 
78	1361	Пациент-13	1955-08-19	ж 	ул. Энтузиастов, 45	+7916121125 	+7917124325 
79	1362	Пациент-13	1995-03-14	м 	ул. Центральная, 29	+7945121516 	+7948124589 
80	1363	Пациент-13	1990-06-21	м 	ул. Лесистая, 10	+7978121516 	+7989124589 
81	1364	Пациент-13	1925-09-25	м 	ул. Строителей, 9	+7916121516 	+7917124589 
82	1365	Пациент-13	1978-01-20	м 	ул. Мелиоративная, 25	+7925121170 	+7925124515 
83	1367	Пациент-13	2000-01-17	ж 	ул. Балтийская, 15	+7916178516 	+7917124458 
84	1368	Пациент-13	1989-01-31	м 	ул. Атлантическая, 19	+793712145  	+7968178989 
85	1369	Пациент-13	1993-07-02	ж 	ул. Абрикосовая, 175	+7918125916 	+7915124459 
86	1370	Пациент-13	1963-04-15	м 	ул. Каштановая, 12	+7916124523 	+7915121245 
87	1371	Пациент-13	1979-11-02	м 	ул. Сливовая, 125	+7925121478 	+7926124156 
88	1372	Пациент-13	1955-08-19	ж 	ул. Энтузиастов, 45	+7916121125 	+7917124325 
89	1373	Пациент-13	1995-03-14	м 	ул. Центральная, 29	+7945121516 	+7948124589 
90	1404	Пациент-13	1925-09-25	м 	ул. Строителей, 9	+7916121516 	+7917124589 
91	1405	Пациент-13	1978-01-20	м 	ул. Мелиоративная, 25	+7925121170 	+7925124515 
92	1406	Пациент-13	2000-01-17	ж 	ул. Балтийская, 15	+7916178516 	+7917124458 
93	1407	Пациент-13	1989-01-31	м 	ул. Атлантическая, 19	+793712145  	+7968178989 
94	1408	Пациент-13	1993-07-02	ж 	ул. Абрикосовая, 175	+7918125916 	+7915124459 
95	1409	Пациент-13	1963-04-15	м 	ул. Каштановая, 12	+7916124523 	+7915121245 
96	1410	Пациент-13	1993-07-02	м 	ул. Сливовая, 125	+7925121478 	+7926124156 
97	1411	Пациент-13	1955-08-19	ж 	ул. Энтузиастов, 45	+7916121125 	+7917124325 
98	1412	Пациент-13	1995-03-14	м 	ул. Центральная, 29	+7945121516 	+7948124589 
99	1413	Пациент-13	1990-06-21	м 	ул. Лесистая, 10	+7978121516 	+7989124589 
100	1414	Пациент-13	1989-01-31	м 	ул. Атлантическая, 19	+793712145  	+7968178989 
101	1415	Пациент-13	1993-07-02	ж 	ул. Абрикосовая, 175	+7918125916 	+7915124459 
102	1416	Пациент-13	1993-07-02	м 	ул. Каштановая, 12	+7916124523 	+7915121245 
103	1417	Пациент-13	1979-11-02	м 	ул. Сливовая, 125	+7925121478 	+7926124156 
104	1418	Пациент-13	1955-08-19	ж 	ул. Энтузиастов, 45	+7916121125 	+7917124325 
105	1419	Пациент-13	1995-03-14	м 	ул. Центральная, 29	+7945121516 	+7948124589 
106	1420	Пациент-13	1990-06-21	м 	ул. Лесистая, 10	+7978121516 	+7989124589 
107	1421	Пациент-13	1925-09-25	м 	ул. Строителей, 9	+7916121516 	+7917124589 
108	1422	Пациент-13	1978-01-20	м 	ул. Мелиоративная, 25	+7925121170 	+7925124515 
109	1423	Пациент-13	2000-01-17	ж 	ул. Балтийская, 15	+7916178516 	+7917124458 
110	1424	Пациент-13	1989-01-31	м 	ул. Атлантическая, 19	+793712145  	+7968178989 
111	1425	Пациент-13	1993-07-02	ж 	ул. Абрикосовая, 175	+7918125916 	+7915124459 
112	1426	Пациент-13	1963-04-15	м 	ул. Каштановая, 12	+7916124523 	+7915121245 
113	1427	Пациент-13	1979-11-02	м 	ул. Сливовая, 125	+7925121478 	+7926124156 
114	1428	Пациент-13	1955-08-19	ж 	ул. Энтузиастов, 45	+7916121125 	+7917124325 
115	1429	Пациент-13	1995-03-14	м 	ул. Центральная, 29	+7945121516 	+7948124589 
116	1234/2023	Иванов Иван Иванович	1978-01-10	m 	\N	\N	\N
118	5555	Стогов	2023-07-06	m 	\N	\N	\N
119	8890	Сапрунов Сергей	2023-07-06	m 	\N	\N	\N
120	455	Носов Андрей	2023-07-06	m 	\N	\N	\N
121	3456	Храпов Сеня	2023-07-06	m 	\N	\N	\N
13	1236	Пациент-13	1978-01-20	м 	ул. Мелиоративная, 25	+7925121175 	+7925124515 
122	54321	Незнайкин	2023-11-10	м 	Цветочный город	+79586458999	+79586958478
123	12345/2024	Иванов	0001-01-01	m 	\N	\N	\N
124	455/2024	арсений 	0001-01-01	m 	\N	\N	\N
125	566/2024	сидоров	2024-02-02	m 	\N	\N	\N
126	1645/2024	Ирнен	2024-05-02	m 	\N	\N	\N
127	1802/2024	Денисов	2024-05-02	m 	\N	\N	\N
128	1811.2024	Сергеев А.А	2024-05-02	m 	\N	\N	\N
129	1815/2024	Сергеева А.А	2024-05-02	м 	\N	\N	\N
130	1910/2024|	Пенев	2024-05-02	m 	\N	\N	\N
117	3434	Брегов Сергей Лукич	2023-07-06	m 	\N	\N	\N
\.


--
-- TOC entry 3535 (class 0 OID 16700)
-- Dependencies: 223
-- Data for Name: room; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.room (room_id, room_numb, room_name, block_id, php_session, doctor_id, date_time, mode_app_id) FROM stdin;
2	2	Операционная № 3	2	unknown	\N	\N	\N
3	3	Операционная № 4	2	unknown	\N	\N	\N
4	4	Операционная № 5	2	unknown	\N	\N	\N
5	5	Палата реанимации № 1	3	unknown	\N	\N	\N
6	6	Палата реанимации № 2	3	unknown	\N	\N	\N
8	8	Пост медсестры-1	4	unknown	\N	\N	\N
9	9	Ординаторская-2	5	unknown	\N	\N	\N
10	10	Пост медсестры-2	5	unknown	\N	\N	\N
7	7	Ординаторская-1	4	unknown	8	\N	\N
1	1	Операционная № 2	2	PHPSESSID=2p9btsn240ntvdh9re0soo56f0	8	2024-10-10 16:08:07.887885	1
\.


--
-- TOC entry 3563 (class 0 OID 16931)
-- Dependencies: 251
-- Data for Name: signal_param; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.signal_param (signal_id, group_id, signal_name, signal_descr_rus, signal_descr_eng, signal_unit, signal_min, signal_max, status_param) FROM stdin;
2	1	HEMD.ABP.D	диастолическое давление	diastolic pressure	мм.рт.с	0	200	0
3	1	HEMD.ABP.M	среднее давление	mean pressure	мм.рт.с	0	200	0
4	1	HEMD.NBP.S	неинвазивное систотолическое давление	non-invasive systolic pressure	мм.рт.с	0	200	0
5	1	HEMD.NBP.D	неинвазивное диастолическое давление	non-invasive diastolic pressure	мм.рт.с	0	200	0
6	1	HEMD.NBP.M	неинвазивное среднее давление	non-invasive mean pressure	мм.рт.с	0	200	0
7	1	HEMD.INVBP.S	инвазивное систолическое давление	invasive systolic pressure	мм.рт.с	0	200	0
8	1	HEMD.INVBP.D	инвазивное диастолическое давление	invasive diastolic pressure	мм.рт.с	0	200	0
9	1	HEMD.INVBP.M	инвазивное среднее давление	invasive mean pressure	мм.рт.с	0	200	0
10	1	HEMD.PAP.S	систолическое давление	systolic pressure	мм.рт.с	0	200	0
11	1	HEMD.PAP.D	диастолическое давление	diastolic pressure	мм.рт.с	0	200	0
12	1	HEMD.PAP.M	среднее давление	mean pressure	мм.рт.с	0	200	0
13	1	HEMD.RAP.S	 систолическое давление	systolic pressure	мм.рт.с	0	200	0
14	1	HEMD.RAP.D	диастолическое давление	diastolic pressure	мм.рт.с	0	200	0
15	1	HEMD.RAP.M	 среднее давление	mean pressure	мм.рт.с	0	200	0
16	1	HEMD.LAP.S	 систолическое давление	systolic pressure	мм.рт.с	0	200	0
17	1	HEMD.LAP.D	диастолическое давление	diastolic pressure	мм.рт.с	0	200	0
18	1	HEMD.LAP.M	 среднее давление	mean pressure	мм.рт.с	0	200	0
19	1	HEMD.ICP.S	 систолическое давление	systolic pressure	мм.рт.с	0	200	0
20	1	HEMD.ICP.D	диастолическое давление	diastolic pressure	мм.рт.с	0	200	0
21	1	HEMD.ICP.M	среднее давление	mean pressure	мм.рт.с	0	200	0
22	1	HEMD.PULS	пульс	pulse	раз.мин	0	300	0
23	5	CONC.CO2_ET	CO2	CO2	%	0	100	0
24	5	CONC.N2O_ET	NO2	NO2	%	0	100	0
25	5	CONC.N2O_Insp	NO2 Insp	NO2 Insp	%	0	100	0
26	5	CONC.O2_Insp	NO2 Insp	NO2 Insp	%	0	100	0
29	5	CONC.N20_INSP	N2O Insp	N2O Ensp	%	0	100	0
30	5	CONC.02_INSP	O2 Insp	O2 Ensp	%	0	100	0
37	5	ANST.DYNAMIC_COMPLIANCE	ANST.DYNAMIC_COMPLIANCE	ANST.DYNAMIC_COMPLIANCE	L/bar	0	100	0
38	5	ANST.PLATEAU_TIME	время полки	time plat	секунд	0	100	0
39	5	ANST.SPONTANEOUS_INSPIRATORY_TIME	спонтанное время вдоха	SPONTANEOUS INSPIRATORY TIME	секунд	0	100	0
40	5	ANST.MEAN_BREATHING_PRESSURE	давление 	 PRESSURE	mBar	0	100	0
41	5	ANST.PLATEAU_PRESSURE	давление 	 PRESSURE	mBar	0	100	0
42	5	ANST.INSPIRATORY_PEAK_FLOW	давление 	 PRESSURE	mBar	0	100	0
43	5	ANST.PEEP_BREATHING_PRESSURE	давление 	 PRESSURE	mBar	0	100	0
44	5	ANST.PEAK_INSPIRATORY_PRESSURE	давление 	 PRESSURE	mBar	0	100	0
45	5	ANST.TIDAL_VOLUME	оьбем	VOLUME	mL	0	100	0
46	5	ANST.SPONTANEOUS_RESPIRATORY_RATE	частота вдоха спонтанная	SPONTANEOUS RESPIRATORY RATE	1/min	0	50	0
47	5	ANST.SPONTANEOUS_MINUTE_VOLUME	обьем вздоха 	SPONTANEOUS MINUTE VOLUME	L/min	0	50	0
48	5	ANST.RESPIRATORY_MINUTE_VOLUME	обьем вздоха 	SPONTANEOUS MINUTE VOLUME	L/min	0	50	0
49	5	ANST.RESPIRATORY_MINUTE_VOLUME_FRAC	обьем вздоха 	 MINUTE VOLUME FRAC	L/min	0	50	0
50	5	ANST.RR	частота вздоха 	raspiration rate	1/min	0	50	0
51	5	ANST.ITOE_IPART	ITOE_IPART 	ITOE_IPART	1/min	0	50	0
52	5	ANST.ITOE_EPART	ETOE_IPART 	ETOE_IPART	1/min	0	50	0
53	5	ANST.FiO2	FiO2 	FiO2	%	0	50	0
54	5	ANST.EtO2	EtO2 	EtO2	%	0	30	0
55	5	ANST.FICO2	FICO2 	FICO2	%	0	30	0
56	5	ANST.ETCO2	ETCO2	ETCO2	%	0	30	0
61	7	ECGR.LEAD.I	отвод I	lead 1	mV	0	1000	0
62	7	ECGR.LEAD.II	отвод II	lead II	mV	0	1000	0
63	7	ECGR.LEAD.III	отвод III	lead III	mV	0	1000	0
64	7	ECGR.LEAD.V	отвод V	lead V	mV	0	1000	0
65	7	ECGR.LEAD.V1	отвод V1	lead V1	mV	0	1000	0
66	7	ECGR.LEAD.V2	отвод V2	lead V2	mV	0	1000	0
67	7	ECGR.LEAD.V3	отвод V3	lead V3	mV	0	1000	0
68	7	ECGR.LEAD.V4	отвод V4	lead V4	mV	0	1000	0
69	7	ECGR.LEAD.V4	отвод V4	lead V4	mV	0	1000	0
70	7	ECGR.LEAD.V5	отвод V5	lead V5	mV	0	1000	0
71	7	ECGR.LEAD.V6	отвод V6	lead V6	mV	0	1000	0
57	2	TEMP.TEMP	температура	temperature	C	0	30	1
1	1	HEMD.ABP.S	Сист. давление	systolic pressure	мм.рт.с	0	200	0
58	2	TEMP.RECT	температура	temperature	C	0	30	1
59	2	TEMP.CORE	температура	temperature	C	0	30	1
60	2	TEMP.SKIN	температура кожи	temperature skin	C	0	30	1
72	7	ECGR.LEAD.AVL	отвод AVL	lead AVL	mV	0	1000	0
73	7	ECGR.LEAD.AVR	отвод AVR	lead AVR	mV	0	1000	0
74	7	ECGR.LEAD.RVP	отвод RVP	lead RVP	mV	0	1000	0
75	4	POXM.PLETH	плетизмограмм	pleth	%	0	50	0
76	4	POXM.SPO2	o2	o2	%	0	100	0
77	7	ECGR.HR	пульс 	pulse	1/мин	0	250	0
80	3	PULSE	Просто пульс-3	Просто пульс-3	\N	\N	\N	0
82	6	ANEST	Просто анестезия-1	Просто анестезия-1	\N	\N	\N	0
83	6	ANEST	Просто анестезия-2	Просто анестезия-2	\N	\N	\N	0
84	6	ANEST	Просто анестезия-3	Просто анестезия-3	\N	\N	\N	0
79	3	PULSE1	Просто пульс-2	Просто пульс-2	\N	\N	\N	0
78	3	PULSE2	Просто пульс-1	Просто пульс-1	\N	\N	\N	0
\.


--
-- TOC entry 3549 (class 0 OID 16821)
-- Dependencies: 237
-- Data for Name: signals; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.signals (signals_id, bed_id, signal_id, signals_date_time, signals_value) FROM stdin;
\.


--
-- TOC entry 3529 (class 0 OID 16663)
-- Dependencies: 217
-- Data for Name: spec; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.spec (spec_id, spec_numb, spec_name) FROM stdin;
1	001	Не выбрана
2	002	Нейрохирург
3	003	Офтальмолог
4	004	Уролог
5	005	Врач-эндоскопист
6	006	Врач УЗИ-диагностики
7	007	Врач МРТ-диагностики
8	008	Врач-реаниматолог
\.


--
-- TOC entry 3531 (class 0 OID 16672)
-- Dependencies: 219
-- Data for Name: status; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.status (status_id, status_numb, status_name) FROM stdin;
1	001	Не выбран
2	002	Работает
3	003	Временно не работает
4	004	Уволен
\.


--
-- TOC entry 3539 (class 0 OID 16718)
-- Dependencies: 227
-- Data for Name: status_bed; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.status_bed (status_id, status_numb, status_name) FROM stdin;
1	0	Свободно
2	1	Занято
\.


--
-- TOC entry 3547 (class 0 OID 16805)
-- Dependencies: 235
-- Data for Name: storage; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.storage (storage_id, storage_numb, storage_path, description) FROM stdin;
1	1	/C	\N
\.


--
-- TOC entry 3543 (class 0 OID 16752)
-- Dependencies: 231
-- Data for Name: study; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.study (study_id, study_numb, patient_id, doctor_id, bed_id, date_beg, date_end, time_beg, time_end, study_descr, study_text) FROM stdin;
1	01	1	2	1	1995-01-01	1995-01-02	00:00:00	00:00:00	Нейрохирургическая операция	\N
2	02	2	2	2	2000-05-10	2000-05-11	00:00:00	00:00:00	Нейрохирургическая операция	\N
3	03	3	3	3	1998-12-01	1998-12-02	00:00:00	00:00:00	Офтальмологическая операция	\N
4	04	4	4	4	2010-04-05	2010-04-06	00:00:00	00:00:00	Урологическая операция	\N
5	05	5	5	5	2005-12-15	2005-12-16	00:00:00	00:00:00	Эндоскопическая операция	\N
6	06	6	8	6	1992-07-04	1992-07-05	00:00:00	00:00:00	Эндоскопическая операция	\N
8	\N	1	4	5	2023-04-04	\N	13:08:45	\N	Не составлено	\N
7	\N	13	4	1	2023-04-04	2023-04-10	13:08:19	08:18:48	Не составлено	\N
9	\N	13	3	1	2023-04-10	2023-04-10	12:04:01	12:04:52	klklk	\N
10	\N	13	4	1	2023-04-10	2023-04-10	12:31:00	12:31:04	dfdfd	\N
11	\N	13	4	1	2023-04-10	2023-04-10	12:32:15	12:32:17	dd	\N
12	\N	13	2	4	2023-04-10	2023-04-10	15:03:35	15:03:37	Не составлено	\N
13	\N	13	4	1	2023-04-10	2023-04-10	15:04:58	15:05:01	Не составлено	\N
14	\N	13	3	1	2023-04-10	2023-04-10	15:06:52	15:06:55	Не составлено	\N
15	\N	13	3	1	2023-04-10	2023-04-10	15:08:56	15:08:58	Не составлено	\N
16	\N	13	3	1	2023-04-10	2023-04-10	15:09:45	15:09:50	Не составлено	\N
17	\N	13	3	1	2023-04-10	2023-04-10	15:10:35	15:10:38	Не составлено	\N
18	\N	13	3	1	2023-04-10	2023-04-10	15:11:15	15:11:17	Не составлено	\N
19	\N	13	3	1	2023-04-10	2023-04-10	15:21:48	15:21:50	Не составлено	\N
20	\N	13	3	2	2023-04-10	2023-04-10	16:15:25	16:15:29	Не составлено	\N
21	\N	13	4	2	2023-04-10	2023-04-10	16:23:27	16:23:30	Не составлено	\N
22	\N	13	3	2	2023-04-10	2023-04-10	16:35:29	16:36:38	Не составлено	\N
23	\N	13	3	2	2023-04-10	2023-04-10	16:36:36	16:36:38	Не составлено	\N
31	\N	119	1	1	2023-06-07	\N	15:02:44.403414	\N	\N	\N
32	\N	120	1	1	2023-06-07	\N	15:07:01.142627	\N	\N	\N
71	\N	13	5	1	2023-08-29	2023-08-29	15:51:32	15:51:46	j	\N
46	\N	5	2	6	2023-08-17	\N	15:14:34	\N	ssss	\N
49	\N	1	4	2	2023-08-17	\N	16:47:59	\N	ee	\N
50	\N	9	3	5	2023-08-17	\N	16:48:21	\N	ee	\N
40	\N	13	2	4	2023-08-17	2023-08-23	15:03:36	11:14:56	gg	\N
51	\N	13	5	4	2023-08-23	2023-08-23	10:04:28	11:14:56	ee	\N
53	\N	5	8	5	2023-08-23	2023-08-23	11:22:42	11:29:09	fgfg	\N
39	\N	13	6	6	2023-08-17	2023-08-23	14:53:08	11:29:19	f	\N
45	\N	13	5	6	2023-08-17	2023-08-23	15:14:18	11:29:19	ssssss	\N
55	\N	13	2	6	2023-08-23	2023-08-23	11:26:25	11:29:19	qq	\N
54	\N	13	2	4	2023-08-23	2023-08-23	11:25:16	11:29:21	qq	\N
41	\N	13	3	3	2023-08-17	2023-08-23	15:05:45	11:29:23	qqq	\N
56	\N	13	3	3	2023-08-23	2023-08-23	11:28:12	11:29:23	f	\N
36	\N	13	8	2	2023-08-17	2023-08-23	13:18:50	11:29:25	17 августа	\N
38	\N	13	5	2	2023-08-17	2023-08-23	13:42:31	11:29:25	qqqqqq	\N
42	\N	13	3	2	2023-08-17	2023-08-23	15:06:21	11:29:25	wwww	\N
43	\N	13	3	2	2023-08-17	2023-08-23	15:08:13	11:29:25	dd	\N
57	\N	13	3	2	2023-08-23	2023-08-23	11:28:43	11:29:25	f	\N
44	\N	13	3	1	2023-08-17	2023-08-23	15:13:58	11:29:27	s	\N
52	\N	13	5	1	2023-08-23	2023-08-23	11:20:34	11:29:27	fg	\N
62	\N	13	4	6	2023-08-23	2023-08-23	12:09:46	12:13:00	f	\N
64	\N	13	4	6	2023-08-23	2023-08-23	12:13:34	12:22:40	q	\N
63	\N	13	4	3	2023-08-23	2023-08-23	12:12:05	12:27:17	s	\N
66	\N	13	3	3	2023-08-23	2023-08-23	12:28:10	12:29:09	j	\N
65	\N	13	2	6	2023-08-23	2023-08-23	12:23:34	13:22:18	g	\N
72	\N	13	5	1	2023-08-29	2023-08-29	15:52:29	15:52:40	j	\N
60	\N	13	4	2	2023-08-23	2023-08-29	11:46:39	15:53:02	q	\N
68	35345/2023\n	1	8	1	2023-08-23	2023-08-23	13:22:37	13:24:01	Описание	\N
73	\N	13	5	2	2023-08-29	2023-08-29	15:52:52	15:53:02	j	\N
33	\N	121	1	7	2023-06-05	2023-06-05	18:21:00.96604	18:21:30.596947	\N	\N
59	\N	13	4	4	2023-08-23	2023-08-28	11:30:57	09:50:03	v	\N
58	\N	13	3	1	2023-08-23	2023-08-29	11:29:32	15:48:08	f	\N
69	\N	13	2	1	2023-08-29	2023-08-29	15:46:53	15:48:08	jjj	\N
70	\N	5	3	4	2023-08-29	2023-08-29	15:47:55	15:48:10	kkk	\N
74	\N	13	5	3	2023-08-29	2023-08-29	15:53:13	15:53:38	j	\N
75	\N	13	5	4	2023-08-29	2023-08-29	15:53:49	15:53:58	j	\N
35	\N	13	8	5	2023-08-16	2023-08-29	17:00:14	15:54:19	55	\N
61	\N	13	4	5	2023-08-23	2023-08-29	11:52:02	15:54:19	q	\N
76	\N	13	5	5	2023-08-29	2023-08-29	15:54:09	15:54:19	j	\N
77	\N	13	5	6	2023-08-29	2023-08-29	15:54:29	15:54:38	j	\N
78	\N	13	5	1	2023-08-29	2023-08-30	15:54:49	10:59:02	j	\N
79	\N	5	5	5	2023-08-29	2023-08-30	15:55:10	10:59:04	j	\N
80	\N	13	6	1	2023-08-30	2023-08-30	10:59:16	17:15:58	шшш	\N
81	\N	13	5	4	2023-08-30	2023-08-30	12:48:47	17:20:46		\N
48	\N	7	4	1	2023-08-17	2023-08-31	16:44:57	09:42:59	fgfg	\N
84	\N	7	4	1	2023-08-30	2023-08-31	17:16:17	09:42:59	dfd	\N
85	\N	13	3	4	2023-08-30	2023-08-31	17:20:58	09:43:02	d	\N
83	\N	13	4	5	2023-08-30	2023-08-31	13:31:30	09:43:04	fgffffgffg	\N
82	\N	13	4	6	2023-08-30	2023-08-31	13:07:44	09:43:05		\N
87	\N	13	3	1	2023-08-31	2023-08-31	12:22:21	12:22:30		\N
88	\N	13	5	6	2023-08-31	2023-08-31	12:29:12	13:35:21	ап	\N
89	\N	13	4	5	2023-08-31	2023-09-01	12:30:34	13:57:03		\N
86	\N	13	6	2	2023-08-31	2023-09-01	09:43:18	13:57:05		\N
90	\N	1	4	1	2023-09-01	2023-09-04	13:57:31	15:32:10	rr	\N
91	\N	5	3	5	2023-09-01	2023-09-04	13:57:40	16:32:21	ff	\N
93	\N	4	4	4	2023-09-04	2023-09-04	16:31:26	16:32:25		\N
94	\N	5	4	5	2023-09-04	2023-09-06	16:49:14	15:44:10		\N
67	\N	3	2	3	2023-08-23	2023-09-07	12:33:13	09:19:21	d	\N
37	\N	5	4	2	2023-08-17	2024-02-26	13:36:49	14:41:16	xxxxx	\N
47	\N	7	3	4	2023-08-17	2024-08-28	16:31:54	15:10:02	sdsss	\N
92	\N	13	2	2	2023-09-04	2023-09-05	15:32:53	15:03:40		\N
95	\N	1	4	1	2023-09-05	2023-09-06	15:03:53	15:44:08	ioiioi	\N
97	\N	6	3	6	2023-09-06	2023-09-06	15:44:27	16:46:36		\N
96	\N	13	4	2	2023-09-06	2023-09-06	15:44:19	16:46:49	h	\N
100	\N	3	4	3	2023-09-06	2023-09-07	17:13:10	09:19:21		\N
101	\N	6	3	6	2023-09-07	2023-09-07	09:20:20	09:20:38		\N
98	\N	2	4	2	2023-09-06	2023-09-07	16:46:58	09:37:41		\N
103	\N	2	3	2	2023-09-07	2023-09-07	09:37:50	09:47:54		\N
99	\N	4	3	4	2023-09-06	2023-09-07	16:47:05	09:47:56		\N
102	\N	1	3	1	2023-09-07	2023-09-07	09:24:43	11:15:40		\N
105	\N	1	4	1	2023-09-07	\N	11:19:47	\N		\N
106	\N	5	3	4	2023-09-21	\N	16:42:03	\N		\N
108	\N	124	1	3	2024-01-30	2024-01-30	18:42:54.017329	18:44:11.141707	\N	\N
107	\N	123	1	3	2024-01-30	2024-01-30	18:15:01.701425	18:51:49.918932	\N	\N
109	\N	13	4	2	2024-01-31	2024-02-01	15:23:45	11:19:13		\N
110	\N	5	3	1	2024-02-01	2024-02-01	11:19:26	11:19:41		\N
112	\N	125	1	1	2024-02-02	2024-02-02	13:08:31.334055	13:10:35.914968	\N	\N
113	\N	126	1	4	2024-02-05	2024-02-05	16:50:44.551648	16:52:03.237707	\N	\N
114	\N	127	1	4	2024-02-05	2024-02-05	18:02:41.505667	18:03:20.727768	\N	\N
115	\N	128	1	4	2024-02-05	2024-02-05	18:12:20.682547	18:12:38.746325	\N	\N
116	\N	129	1	4	2024-02-05	2024-02-05	18:15:45.663835	18:16:27.668382	\N	\N
117	\N	130	1	4	2024-02-05	2024-02-05	19:10:33.042297	19:10:48.955185	\N	\N
111	\N	5	3	1	2024-02-01	2024-02-06	11:19:55	13:58:25		\N
119	\N	5	4	3	2024-02-06	2024-02-06	14:01:38	15:21:11		\N
120	\N	13	3	6	2024-02-06	2024-02-06	14:12:55	15:30:47		\N
121	\N	3	4	4	2024-02-06	2024-02-08	15:30:59	11:33:00		\N
118	\N	13	2	2	2024-02-06	2024-02-08	13:58:53	11:33:21		\N
125	\N	3	4	3	2024-02-08	2024-02-08	12:44:00	13:06:26		\N
124	\N	2	3	2	2024-02-08	2024-02-08	12:42:50	13:06:28		\N
122	\N	4	3	6	2024-02-08	2024-02-08	11:33:10	13:06:29		\N
127	\N	13	3	4	2024-02-21	2024-02-21	14:12:50	14:14:30		\N
128	\N	13	3	5	2024-02-21	2024-02-21	14:14:56	15:34:19		\N
123	\N	13	4	1	2024-02-08	2024-02-26	11:33:28	14:31:49		\N
126	\N	5	4	2	2024-02-09	2024-02-26	16:04:40	14:41:16		\N
129	\N	13	5	1	2024-02-26	2024-02-26	14:38:56	14:43:35		\N
131	\N	5	5	1	2024-02-26	2024-02-26	14:43:48	14:45:19		\N
130	\N	13	3	2	2024-02-26	2024-02-26	14:43:28	14:45:33		\N
133	\N	3	5	2	2024-02-26	\N	14:46:27	\N		\N
104	\N	4	4	4	2023-09-07	2024-03-01	11:15:33	15:26:10		\N
135	\N	4	4	4	2024-03-01	2024-03-01	15:18:29	15:26:10		\N
140	\N	13	5	4	2024-03-29	2024-04-01	11:54:08	13:48:38		\N
136	\N	13	3	5	2024-03-04	2024-04-01	11:35:24	13:48:41		\N
139	\N	13	3	5	2024-03-29	2024-04-01	11:47:26	13:48:41		\N
141	\N	13	4	4	2024-04-23	2024-04-23	14:25:58	14:26:04	Не составлено	\N
134	\N	2	4	2	2024-02-26	2024-05-15	15:56:40	14:29:12		\N
132	\N	13	3	1	2024-02-26	2024-07-23	14:46:14	13:33:50		\N
137	\N	13	3	1	2024-03-28	2024-07-23	15:18:32	13:33:50		\N
138	\N	13	3	1	2024-03-28	2024-07-23	15:37:19	13:33:50		\N
143	\N	5	4	5	2024-07-23	2024-07-23	13:42:57	13:43:14		\N
142	\N	2	3	2	2024-05-17	2024-08-28	12:19:29	12:46:34		\N
146	\N	1	2	4	2024-08-28	2024-08-28	12:53:59	12:54:41		\N
147	\N	1	8	4	2024-08-28	2024-08-28	12:59:18	13:05:09		\N
149	\N	5	2	5	2024-08-28	2024-08-28	13:16:39	15:09:58		\N
148	\N	7	3	4	2024-08-28	2024-08-28	13:16:22	15:10:02		\N
154	\N	6	5	5	2024-08-28	\N	16:16:31	\N		\N
155	\N	13	5	5	2024-08-28	\N	16:17:33	\N		\N
156	\N	8	3	5	2024-08-28	2024-10-02	16:18:04	11:09:40		\N
153	\N	4	6	4	2024-08-28	2024-10-02	16:16:09	11:09:42		\N
152	\N	9	4	3	2024-08-28	2024-10-02	16:15:45	11:09:44		\N
145	\N	13	4	2	2024-08-28	2024-10-02	12:47:36	11:09:45		\N
158	\N	13	6	2	2024-10-02	2024-10-02	11:05:53	11:09:45		\N
159	\N	13	8	2	2024-10-02	2024-10-02	11:07:00	11:09:45		\N
157	\N	13	4	1	2024-10-01	2024-10-02	13:35:48	11:09:48		\N
160	\N	13	2	2	2024-10-02	\N	11:10:08	\N		\N
162	\N	1	4	1	2024-10-02	\N	12:07:59	\N		\N
163	\N	5	3	5	2024-10-02	2024-10-02	12:08:28	12:11:10		\N
144	\N	3	5	3	2024-08-28	2024-10-02	12:46:18	12:11:29		\N
164	\N	3	2	3	2024-10-02	2024-10-02	12:11:26	12:11:29		\N
\.


--
-- TOC entry 3557 (class 0 OID 16870)
-- Dependencies: 245
-- Data for Name: videos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.videos (videos_id, storage_id, bed_id, doctor_id, videos_date_time_beg, videos_date_time_end, video_cnt, video_comments) FROM stdin;
1	1	1	2	2021-12-12 12:12:12	2022-01-01 01:01:01	0	video_comments
\.


--
-- TOC entry 3545 (class 0 OID 16776)
-- Dependencies: 233
-- Data for Name: worklist; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.worklist (worklist_id, worklist_numb, patient_id, doctor_id, room_id, block_id, date_beg, date_end, time_beg, time_end, worklist_descr, worklist_text) FROM stdin;
1	01	1	2	1	2	1995-01-01	\N	00:00:00	\N	Проверочная запись	\N
2	02	2	2	2	3	2000-05-10	\N	00:00:00	\N	Нейрохирургическая операция	\N
3	03	3	3	3	4	1998-12-01	\N	00:00:00	\N	Офтальмологическая операция	\N
4	04	4	4	4	5	2010-04-05	\N	00:00:00	\N	Урологическая операция	\N
5	05	5	5	5	5	2005-12-15	\N	00:00:00	\N	Эндоскопическая операция	\N
6	06	6	8	6	5	1992-07-04	\N	00:00:00	\N	Эндоскопическая операция	\N
7	07	7	2	1	2	1995-01-02	\N	00:00:00	\N	Нейрохирургическая операция	\N
8	08	8	2	1	2	1995-01-01	\N	00:00:00	\N	Нейрохирургическая операция	\N
9	09	9	3	2	2	1998-12-01	\N	00:00:00	\N	Офтальмологическая операция	\N
10	10	10	4	4	3	2010-04-05	\N	00:00:00	\N	Урологическая операция	\N
11	11	11	4	2	4	2011-10-08	\N	00:00:00	\N	Урологическая операция	\N
12	12	12	5	4	5	2015-12-20	\N	00:00:00	\N	Эндоскопическая операция	\N
13	\N	60	5	4	3	2023-11-10	2023-11-11	11:18:00	14:21:00	Jgbcfybt	\N
14	\N	117	4	2	2	2024-04-18	2024-04-19	13:40:00	13:44:00	Описание, так описание!	\N
\.


--
-- TOC entry 3594 (class 0 OID 0)
-- Dependencies: 240
-- Name: alarm_param_alarm_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.alarm_param_alarm_id_seq', 10, true);


--
-- TOC entry 3595 (class 0 OID 0)
-- Dependencies: 242
-- Name: alarms_alarms_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.alarms_alarms_id_seq', 2036271, true);


--
-- TOC entry 3596 (class 0 OID 0)
-- Dependencies: 228
-- Name: bed_bed_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.bed_bed_id_seq', 10, true);


--
-- TOC entry 3597 (class 0 OID 0)
-- Dependencies: 224
-- Name: block_block_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.block_block_id_seq', 5, true);


--
-- TOC entry 3598 (class 0 OID 0)
-- Dependencies: 238
-- Name: color_color_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.color_color_id_seq', 9, true);


--
-- TOC entry 3599 (class 0 OID 0)
-- Dependencies: 220
-- Name: doctor_doctor_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.doctor_doctor_id_seq', 9, true);


--
-- TOC entry 3600 (class 0 OID 0)
-- Dependencies: 248
-- Name: grup_group_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.grup_group_id_seq', 4, true);


--
-- TOC entry 3601 (class 0 OID 0)
-- Dependencies: 246
-- Name: images_images_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.images_images_id_seq', 567631, true);


--
-- TOC entry 3602 (class 0 OID 0)
-- Dependencies: 252
-- Name: list_list_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.list_list_id_seq', 2, true);


--
-- TOC entry 3603 (class 0 OID 0)
-- Dependencies: 254
-- Name: mode_app_mode_app_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.mode_app_mode_app_id_seq', 2, true);


--
-- TOC entry 3604 (class 0 OID 0)
-- Dependencies: 214
-- Name: patient_patient_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.patient_patient_id_seq', 130, true);


--
-- TOC entry 3605 (class 0 OID 0)
-- Dependencies: 222
-- Name: room_room_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.room_room_id_seq', 10, true);


--
-- TOC entry 3606 (class 0 OID 0)
-- Dependencies: 250
-- Name: signal_param_signal_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.signal_param_signal_id_seq', 84, true);


--
-- TOC entry 3607 (class 0 OID 0)
-- Dependencies: 236
-- Name: signals_signals_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.signals_signals_id_seq', 20562840, true);


--
-- TOC entry 3608 (class 0 OID 0)
-- Dependencies: 216
-- Name: spec_spec_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.spec_spec_id_seq', 8, true);


--
-- TOC entry 3609 (class 0 OID 0)
-- Dependencies: 226
-- Name: status_bed_status_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.status_bed_status_id_seq', 2, true);


--
-- TOC entry 3610 (class 0 OID 0)
-- Dependencies: 218
-- Name: status_status_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.status_status_id_seq', 4, true);


--
-- TOC entry 3611 (class 0 OID 0)
-- Dependencies: 234
-- Name: storage_storage_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.storage_storage_id_seq', 1, true);


--
-- TOC entry 3612 (class 0 OID 0)
-- Dependencies: 230
-- Name: study_study_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.study_study_id_seq', 164, true);


--
-- TOC entry 3613 (class 0 OID 0)
-- Dependencies: 244
-- Name: videos_videos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.videos_videos_id_seq', 1, true);


--
-- TOC entry 3614 (class 0 OID 0)
-- Dependencies: 232
-- Name: worklist_worklist_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.worklist_worklist_id_seq', 14, true);


--
-- TOC entry 3342 (class 2606 OID 16850)
-- Name: alarm_param alarm_param_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alarm_param
    ADD CONSTRAINT alarm_param_pkey PRIMARY KEY (alarm_id);


--
-- TOC entry 3344 (class 2606 OID 16858)
-- Name: alarms alarms_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alarms
    ADD CONSTRAINT alarms_pkey PRIMARY KEY (alarms_id);


--
-- TOC entry 3328 (class 2606 OID 16735)
-- Name: bed bed_bed_numb_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bed
    ADD CONSTRAINT bed_bed_numb_key UNIQUE (bed_numb);


--
-- TOC entry 3330 (class 2606 OID 16733)
-- Name: bed bed_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bed
    ADD CONSTRAINT bed_pkey PRIMARY KEY (bed_id);


--
-- TOC entry 3320 (class 2606 OID 16716)
-- Name: block block_block_numb_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.block
    ADD CONSTRAINT block_block_numb_key UNIQUE (block_numb);


--
-- TOC entry 3322 (class 2606 OID 16714)
-- Name: block block_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.block
    ADD CONSTRAINT block_pkey PRIMARY KEY (block_id);


--
-- TOC entry 3340 (class 2606 OID 16843)
-- Name: color color_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.color
    ADD CONSTRAINT color_pkey PRIMARY KEY (color_id);


--
-- TOC entry 3312 (class 2606 OID 16688)
-- Name: doctor doctor_doctor_numb_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.doctor
    ADD CONSTRAINT doctor_doctor_numb_key UNIQUE (doctor_numb);


--
-- TOC entry 3314 (class 2606 OID 16686)
-- Name: doctor doctor_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.doctor
    ADD CONSTRAINT doctor_pkey PRIMARY KEY (doctor_id);


--
-- TOC entry 3350 (class 2606 OID 16929)
-- Name: grup grup_group_numb_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grup
    ADD CONSTRAINT grup_group_numb_key UNIQUE (group_numb);


--
-- TOC entry 3352 (class 2606 OID 16927)
-- Name: grup grup_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grup
    ADD CONSTRAINT grup_pkey PRIMARY KEY (group_id);


--
-- TOC entry 3348 (class 2606 OID 16900)
-- Name: images images_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_pkey PRIMARY KEY (images_id);


--
-- TOC entry 3356 (class 2606 OID 78714)
-- Name: list list_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.list
    ADD CONSTRAINT list_pkey PRIMARY KEY (list_id);


--
-- TOC entry 3358 (class 2606 OID 415977)
-- Name: mode_app mode_app_mode_app_numb_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mode_app
    ADD CONSTRAINT mode_app_mode_app_numb_key UNIQUE (mode_app_numb);


--
-- TOC entry 3360 (class 2606 OID 415975)
-- Name: mode_app mode_app_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mode_app
    ADD CONSTRAINT mode_app_pkey PRIMARY KEY (mode_app_id);


--
-- TOC entry 3300 (class 2606 OID 16661)
-- Name: patient patient_patient_numb_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.patient
    ADD CONSTRAINT patient_patient_numb_key UNIQUE (patient_numb);


--
-- TOC entry 3302 (class 2606 OID 16659)
-- Name: patient patient_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.patient
    ADD CONSTRAINT patient_pkey PRIMARY KEY (patient_id);


--
-- TOC entry 3316 (class 2606 OID 16705)
-- Name: room room_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.room
    ADD CONSTRAINT room_pkey PRIMARY KEY (room_id);


--
-- TOC entry 3318 (class 2606 OID 16707)
-- Name: room room_room_numb_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.room
    ADD CONSTRAINT room_room_numb_key UNIQUE (room_numb);


--
-- TOC entry 3354 (class 2606 OID 16936)
-- Name: signal_param signal_param_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.signal_param
    ADD CONSTRAINT signal_param_pkey PRIMARY KEY (signal_id);


--
-- TOC entry 3338 (class 2606 OID 16826)
-- Name: signals signals_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_pkey PRIMARY KEY (signals_id);


--
-- TOC entry 3304 (class 2606 OID 16668)
-- Name: spec spec_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.spec
    ADD CONSTRAINT spec_pkey PRIMARY KEY (spec_id);


--
-- TOC entry 3306 (class 2606 OID 16670)
-- Name: spec spec_spec_numb_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.spec
    ADD CONSTRAINT spec_spec_numb_key UNIQUE (spec_numb);


--
-- TOC entry 3324 (class 2606 OID 16723)
-- Name: status_bed status_bed_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.status_bed
    ADD CONSTRAINT status_bed_pkey PRIMARY KEY (status_id);


--
-- TOC entry 3326 (class 2606 OID 16725)
-- Name: status_bed status_bed_status_numb_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.status_bed
    ADD CONSTRAINT status_bed_status_numb_key UNIQUE (status_numb);


--
-- TOC entry 3308 (class 2606 OID 16677)
-- Name: status status_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.status
    ADD CONSTRAINT status_pkey PRIMARY KEY (status_id);


--
-- TOC entry 3310 (class 2606 OID 16679)
-- Name: status status_status_numb_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.status
    ADD CONSTRAINT status_status_numb_key UNIQUE (status_numb);


--
-- TOC entry 3336 (class 2606 OID 16812)
-- Name: storage storage_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.storage
    ADD CONSTRAINT storage_pkey PRIMARY KEY (storage_id);


--
-- TOC entry 3332 (class 2606 OID 16759)
-- Name: study study_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.study
    ADD CONSTRAINT study_pkey PRIMARY KEY (study_id);


--
-- TOC entry 3346 (class 2606 OID 16876)
-- Name: videos videos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_pkey PRIMARY KEY (videos_id);


--
-- TOC entry 3334 (class 2606 OID 16783)
-- Name: worklist worklist_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.worklist
    ADD CONSTRAINT worklist_pkey PRIMARY KEY (worklist_id);


--
-- TOC entry 3377 (class 2606 OID 16864)
-- Name: alarms alarm_param_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alarms
    ADD CONSTRAINT alarm_param_fk FOREIGN KEY (alarm_id) REFERENCES public.alarm_param(alarm_id) ON DELETE RESTRICT;


--
-- TOC entry 3369 (class 2606 OID 16765)
-- Name: study bed_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.study
    ADD CONSTRAINT bed_fk FOREIGN KEY (bed_id) REFERENCES public.bed(bed_id) ON DELETE RESTRICT;


--
-- TOC entry 3376 (class 2606 OID 16827)
-- Name: signals bed_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT bed_fk FOREIGN KEY (bed_id) REFERENCES public.bed(bed_id) ON DELETE RESTRICT;


--
-- TOC entry 3378 (class 2606 OID 16859)
-- Name: alarms bed_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alarms
    ADD CONSTRAINT bed_fk FOREIGN KEY (bed_id) REFERENCES public.bed(bed_id) ON DELETE RESTRICT;


--
-- TOC entry 3379 (class 2606 OID 16877)
-- Name: videos bed_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT bed_fk FOREIGN KEY (bed_id) REFERENCES public.bed(bed_id) ON DELETE RESTRICT;


--
-- TOC entry 3382 (class 2606 OID 16901)
-- Name: images bed_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT bed_fk FOREIGN KEY (bed_id) REFERENCES public.bed(bed_id) ON DELETE RESTRICT;


--
-- TOC entry 3366 (class 2606 OID 16736)
-- Name: bed block_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bed
    ADD CONSTRAINT block_fk FOREIGN KEY (block_id) REFERENCES public.block(block_id) ON DELETE RESTRICT;


--
-- TOC entry 3372 (class 2606 OID 16794)
-- Name: worklist block_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.worklist
    ADD CONSTRAINT block_fk FOREIGN KEY (block_id) REFERENCES public.block(block_id) ON DELETE RESTRICT;


--
-- TOC entry 3370 (class 2606 OID 16770)
-- Name: study doctor_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.study
    ADD CONSTRAINT doctor_fk FOREIGN KEY (doctor_id) REFERENCES public.doctor(doctor_id) ON DELETE RESTRICT;


--
-- TOC entry 3373 (class 2606 OID 16799)
-- Name: worklist doctor_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.worklist
    ADD CONSTRAINT doctor_fk FOREIGN KEY (doctor_id) REFERENCES public.doctor(doctor_id) ON DELETE RESTRICT;


--
-- TOC entry 3380 (class 2606 OID 16882)
-- Name: videos doctor_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT doctor_fk FOREIGN KEY (doctor_id) REFERENCES public.doctor(doctor_id) ON DELETE RESTRICT;


--
-- TOC entry 3383 (class 2606 OID 16937)
-- Name: signal_param grup_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.signal_param
    ADD CONSTRAINT grup_fk FOREIGN KEY (group_id) REFERENCES public.grup(group_id) ON DELETE RESTRICT;


--
-- TOC entry 3363 (class 2606 OID 528579)
-- Name: room mode_app_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.room
    ADD CONSTRAINT mode_app_fk FOREIGN KEY (mode_app_id) REFERENCES public.mode_app(mode_app_id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3371 (class 2606 OID 16760)
-- Name: study patient_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.study
    ADD CONSTRAINT patient_fk FOREIGN KEY (patient_id) REFERENCES public.patient(patient_id) ON DELETE RESTRICT;


--
-- TOC entry 3374 (class 2606 OID 16784)
-- Name: worklist patient_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.worklist
    ADD CONSTRAINT patient_fk FOREIGN KEY (patient_id) REFERENCES public.patient(patient_id) ON DELETE RESTRICT;


--
-- TOC entry 3364 (class 2606 OID 16942)
-- Name: room room_block_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.room
    ADD CONSTRAINT room_block_id_fkey FOREIGN KEY (block_id) REFERENCES public.block(block_id) NOT VALID;


--
-- TOC entry 3367 (class 2606 OID 16741)
-- Name: bed room_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bed
    ADD CONSTRAINT room_fk FOREIGN KEY (room_id) REFERENCES public.room(room_id) ON DELETE RESTRICT;


--
-- TOC entry 3375 (class 2606 OID 16789)
-- Name: worklist room_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.worklist
    ADD CONSTRAINT room_fk FOREIGN KEY (room_id) REFERENCES public.room(room_id) ON DELETE RESTRICT;


--
-- TOC entry 3365 (class 2606 OID 526038)
-- Name: room room_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.room
    ADD CONSTRAINT room_fk FOREIGN KEY (doctor_id) REFERENCES public.doctor(doctor_id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 3361 (class 2606 OID 16689)
-- Name: doctor spec_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.doctor
    ADD CONSTRAINT spec_fk FOREIGN KEY (spec_id) REFERENCES public.spec(spec_id) ON DELETE RESTRICT;


--
-- TOC entry 3368 (class 2606 OID 16746)
-- Name: bed status_bed_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bed
    ADD CONSTRAINT status_bed_fk FOREIGN KEY (status_id) REFERENCES public.status_bed(status_id) ON DELETE RESTRICT;


--
-- TOC entry 3362 (class 2606 OID 16694)
-- Name: doctor status_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.doctor
    ADD CONSTRAINT status_fk FOREIGN KEY (status_id) REFERENCES public.status(status_id) ON DELETE RESTRICT;


--
-- TOC entry 3381 (class 2606 OID 16887)
-- Name: videos storage_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT storage_fk FOREIGN KEY (storage_id) REFERENCES public.storage(storage_id) ON DELETE RESTRICT;


-- Completed on 2025-05-15 13:30:07

--
-- PostgreSQL database dump complete
--

