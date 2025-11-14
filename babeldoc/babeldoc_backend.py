# 调用babeldoc的示例命令：
# uv run babeldoc --files babeldoc/2510-20817.pdf --openai --openai-model "gpt-4o-mini" --openai-base-url "https://apis.bltcy.ai/v1" --openai-api-key "sk-wgfnICtif7oeeCuZD3D2E3D09c7a43D6954a697eAb2b8dB7" --glossary-files all_terms.csv
# 输出结果：
# 2510-20817.zh.dual.pdf
# 2510-20817.zh.mono.pdf

# log信息：
# (sparktts) lyl@lyl:~/academic/chinarxiv$ uv run babeldoc --files babeldoc/2510-20817.pdf --openai --openai-model "gpt-4o-mini" --openai-base-url "https://apis.bltcy.ai/v1" --openai-api-key "sk-wgfnICtif7oeeCuZD3D2E3D09c7a43D6954a697eAb2b8dB7"
# [10/26/25 02:02:39] INFO     INFO:babeldoc.docvision.base_doclayout:Loading ONNX model...                                                  base_doclayout.py:43
# [10/26/25 02:02:40] INFO     INFO:babeldoc.docvision.doclayout:Available Provider: CPUExecutionProvider                                         doclayout.py:54
# [10/26/25 02:02:41] INFO     INFO:babeldoc.format.pdf.high_level:start to translate: babeldoc/2510-20817.pdf                                  high_level.py:600
# [10/26/25 02:03:23] INFO     INFO:babeldoc.format.pdf.document_il.midend.automatic_term_extractor:Automatic Term Extraction:    automatic_term_extractor.py:335
#                              Starting term extraction for document.                                                                                            
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.automatic_term_extractor:Error during automatic     automatic_term_extractor.py:329
#                              terms extract: Unterminated string starting at: line 97 column 44 (char 4336)                                                     
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.automatic_term_extractor:Error during automatic     automatic_term_extractor.py:329
#                              terms extract: Expecting value: line 88 column 52 (char 4282)                                                                     
# [10/26/25 02:03:27] INFO     INFO:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Found title paragraph:            il_translator_llm_only.py:112
#                              KL-REGULARIZED REINFORCEMENT LEARNING IS DESIGNED TO MODECOLLAPSE                                                                 
#                     INFO     INFO:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Found first title paragraph:      il_translator_llm_only.py:131
#                              KL-REGULARIZED REINFORCEMENT LEARNING IS DESIGNED TO MODECOLLAPSE                                                                 
# [10/26/25 02:03:28] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator:Too many placeholders (41) in paragraph[ddvHL],  il_translator.py:623
#                              disabling rich text translation for this paragraph                                                                                
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator:Too many placeholders (41) in paragraph[hc3PE],  il_translator.py:623
#                              disabling rich text translation for this paragraph                                                                                
# [10/26/25 02:03:33] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator:Too many placeholders (41) in paragraph[PFy2S],  il_translator.py:623
#                              disabling rich text translation for this paragraph                                                                                
# [10/26/25 02:03:53] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator:Too many placeholders (41) in paragraph[Ym7bx],  il_translator.py:623
#                              disabling rich text translation for this paragraph                                                                                
# [10/26/25 02:03:54] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator:Too many placeholders (41) in paragraph[m3jS5],  il_translator.py:623
#                              disabling rich text translation for this paragraph                                                                                
# [10/26/25 02:03:57] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator:Too many placeholders (41) in paragraph[DwtBU],  il_translator.py:623
#                              disabling rich text translation for this paragraph                                                                                
#                     INFO     INFO:babeldoc.translator.cache:Cleaning up translation cache...                                                       cache.py:134
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator:Too many placeholders (41) in paragraph[AtyDS],  il_translator.py:623
#                              disabling rich text translation for this paragraph                                                                                
# [10/26/25 02:03:58] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator:Too many placeholders (41) in paragraph[Aagtg],  il_translator.py:623
#                              disabling rich text translation for this paragraph                                                                                
# [10/26/25 02:04:09] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator:Too many placeholders (41) in paragraph[rPMwD],  il_translator.py:623
#                              disabling rich text translation for this paragraph                                                                                
# [10/26/25 02:04:10] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator:Too many placeholders (41) in paragraph[pnTtq],  il_translator.py:623
#                              disabling rich text translation for this paragraph                                                                                
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: aV7QG                                                                                                  
# [10/26/25 02:04:16] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is too long il_translator_llm_only.py:857
#                              or too short. Input: 1, Output: 3                                                                                                 
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: bL7Vb                                                                                                  
# [10/26/25 02:04:20] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is too long il_translator_llm_only.py:857
#                              or too short. Input: 1, Output: 3                                                                                                 
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: PpXe6                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is too long il_translator_llm_only.py:857
#                              or too short. Input: 1, Output: 3                                                                                                 
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: sFZSq                                                                                                  
# [10/26/25 02:04:23] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: SASYG                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: HS7xp                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: RpVj7                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: 6bw9V                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: NG7zg                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: 9JMnx                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: VyCy9                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: ogPSd                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: KNs1e                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: j4u1t                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: y6n2t                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: MS4RZ                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: yhJNo                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: XeFd8                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: D6MAB                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: tCfnw                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: uncAi                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: aXa4q                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: J7gqa                                                                                                  
# [10/26/25 02:04:24] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: TZpb9                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: 585W7                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: aLkZA                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: XkKxb                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: eNq8s                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: z48pF                                                                                                  
# [10/26/25 02:04:25] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: qJR5B                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result edit        il_translator_llm_only.py:867
#                              distance is too small. distance: 3, input: Div <style id='1'>(</style>{v3}<style id='4'>)</style>,                                
#                              output: 分 <style id='1'>(</style>{v3}<style id='4'>)</style>                                                                     
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: 6RV43                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: GZtPn                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: LxEyz                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: UKomF                                                                                                  
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is too long il_translator_llm_only.py:857
#                              or too short. Input: 1, Output: 3                                                                                                 
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: pNP6E                                                                                                  
# [10/26/25 02:04:26] WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation result is the same il_translator_llm_only.py:848
#                              as input, fallback.                                                                                                               
#                     WARNING  WARNING:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Fallback to simple             il_translator_llm_only.py:893
#                              translation. paragraph id: NgfaC                                                                                                  
# [10/26/25 02:04:27] INFO     INFO:babeldoc.format.pdf.document_il.midend.il_translator_llm_only:Translation completed. Total:     il_translator_llm_only.py:191
#                              450, Successful: 414, Fallback: 36                                                                                                
# [10/26/25 02:04:39] INFO     INFO:babeldoc.format.pdf.document_il.backend.pdf_creater:Font subsetting completed successfully                pdf_creater.py:1078
# [10/26/25 02:04:40] INFO     INFO:babeldoc.format.pdf.document_il.backend.pdf_creater:PDF save with clean=True completed successfully       pdf_creater.py:1193
# [10/26/25 02:04:41] INFO     INFO:babeldoc.format.pdf.document_il.backend.pdf_creater:PDF save with clean=True completed successfully       pdf_creater.py:1193
# [10/26/25 02:04:42] INFO     INFO:babeldoc.format.pdf.high_level:Peak memory usage: 4310.84 MB                                                high_level.py:478
#                     INFO     INFO:babeldoc.format.pdf.high_level:finish translate: babeldoc/2510-20817.pdf, cost: 121.0284104347229 s         high_level.py:755
# [10/26/25 02:04:44] INFO     INFO:babeldoc.format.pdf.document_il.backend.pdf_creater:PDF save with clean=True completed successfully       pdf_creater.py:1193
#                     INFO     INFO:babeldoc.main:Translation results:                                                                                main.py:719
#                                      Original PDF: babeldoc/2510-20817.pdf                                                                                     
#                                      Total time: 121.03 seconds                                                                                                
#                                      Monolingual PDF: /home/lyl/academic/chinarxiv/2510-20817.zh.mono.pdf                                                      
#                                      Dual-language PDF: /home/lyl/academic/chinarxiv/2510-20817.zh.dual.pdf                                                    
#                                      Peak memory usage: 4310.8359375 MB                                                                                        
# translate                                              ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100/100   0:02:00 0:00:00
#                     INFO     INFO:babeldoc.format.pdf.translation_config:cleanup temp files: /tmp/tmpc6a4xoh2                         translation_config.py:420
# translate                                              ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100/100   0:02:00 0:00:00
# Parse PDF and Create Intermediate Representation (1/1) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 26/26     0:00:07 0:00:00
# DetectScannedFile (1/1)                                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 26/26     0:00:01 0:00:00
# Parse Page Layout (1/1)                                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 52/52     0:00:19 0:00:00
# Parse Paragraphs (1/1)                                 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 26/26     0:00:07 0:00:00
# Parse Formulas and Styles (1/1)                        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 26/26     0:00:01 0:00:00
# Automatic Term Extraction (1/1)                        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 927/927   0:00:00 0:00:00
# Translate Paragraphs (1/1)                             ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 927/927   0:00:59 0:00:00
# Typesetting (1/1)                                      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 52/52     0:00:03 0:00:00
# Add Fonts (1/1)                                        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1448/1448 0:00:00 0:00:00
# Generate drawing instructions (1/1)                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 26/26     0:00:02 0:00:00
# Subset font (1/1)                                      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1/1       0:00:01 0:00:00
# Save PDF (1/1)                                         ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2/2       0:00:02 0:00:00                    INFO     INFO:babeldoc.main:Total tokens: 72495                                                                                 main.py:728
#                     INFO     INFO:babeldoc.main:Prompt tokens: 52197                                                                                main.py:729
#                     INFO     INFO:babeldoc.main:Completion tokens: 20298                                                                            main.py:730
#                     INFO     INFO:babeldoc.main:Cache hit prompt tokens: 0                                                                          main.py:731
#                     INFO     INFO:babeldoc.main:Term extraction tokens: total=0 prompt=0 completion=0 cache_hit_prompt=0                            main.py:734
#                     INFO     INFO:babeldoc.format.pdf.high_level:Waiting for translation to finish...                                         high_level.py:442