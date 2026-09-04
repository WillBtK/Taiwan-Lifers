-- Six-firm panel seed, applied 2026-09-04 via the Supabase MCP. Idempotent.
-- Conventions (decisions 3.10): valid_from marks TLFX panel coverage start
-- (earliest deck, 2011 Q4), not incorporation; ticker is the LIFE COMPANY's
-- own filing code, never the holdco's (decisions 3.5) and stays NULL until
-- verified from a primary document (taiwan_life, shinkong_life pending);
-- shinkong_life keeps one entity_id across the 2026-01-01 merger per README
-- §4.5, with the break recorded in break_note.
insert into tlfx.entities (entity_id, name_en, name_zh, ticker, holding_company_en, holding_company_zh, is_listed, valid_from, valid_to, successor_entity_id, break_note, source_url, source_doc, retrieved_at, vintage) values
('cathay_life','Cathay Life Insurance','國泰人壽','5846','Cathay Financial Holdings (2882)','國泰金控', false, '2011-01-01', null, null,
 'valid_from marks the start of TLFX panel coverage (earliest deck 2011 Q4), not incorporation. Filing code 5846 verified from the company''s own statutory report cover.',
 'https://www.cathayholdings.com/holdings/ir/financial_information/quarterly_reports','README §4.5 entity table; statutory report cover (5846)', now(), '2026-09-04'),
('fubon_life','Fubon Life Insurance','富邦人壽','5865','Fubon Financial Holding (2881)','富邦金控', false, '2011-01-01', null, null,
 'valid_from marks panel coverage start, not incorporation. Filing code 5865 from the company''s filed documents.',
 'https://www.fubon.com/life/Investors/public-info/','README §4.5 entity table', now(), '2026-09-04'),
('nanshan_life','Nan Shan Life Insurance','南山人壽','5874', null, null, false, '2011-01-01', null, null,
 'Unlisted, no financial holding company. valid_from marks panel coverage start. Filing code 5874 from the company''s own MOPS-link page.',
 'https://www.nanshanlife.com.tw/','README §4.5 entity table', now(), '2026-09-04'),
('kgi_life','KGI Life Insurance (China Life until 2023)','凱基人壽（原中國人壽）','2823','KGI Financial Holding (2883)','凱基金控', false, '2011-01-01', null, null,
 'Renamed from China Life Insurance (中國人壽) in 2023 under KGI Financial; same legal entity and filing code 2823 (verified directly against MOPS), so no entity break. Was exchange-listed as 2823 before the holdco share swap.',
 'https://www.kgilife.com.tw/','README §4.5 entity table; MOPS ajax_t164sb04 co_id=2823', now(), '2026-09-04'),
('taiwan_life','Taiwan Life Insurance','台灣人壽', null,'CTBC Financial Holding (2891)','中信金控', false, '2011-01-01', null, null,
 'valid_from marks panel coverage start. Filing code not yet verified from a primary document — do not query filing systems for this entity until it is.',
 'https://ir.ctbcholding.com/html/index','README §4.5 entity table', now(), '2026-09-04'),
('shinkong_life','Shin Kong Life Insurance','新光人壽', null,'TS Financial Holding (2887); Shin Kong FHC (2888) before 2026','台新新光金控（2026年前為新光金控）', false, '2011-01-01', null, null,
 'Panel-continuity convention per README §4.5: entity_id stays stable across the 2026-01-01 merger, recorded here as a break — Taishin Life absorbed Shin Kong Life and the surviving entity took the Shin Kong Life name under TS Financial. Pre-2026 rows are the old Shin Kong Life; from 2026-01 the merged entity. Filing code not yet verified from a primary document.',
 'https://www.tsholdings.com.tw/','README §4.5 entity table; README §2(vii)', now(), '2026-09-04')
on conflict (entity_id) do nothing;
