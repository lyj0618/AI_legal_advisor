<template>
  <div class="kb-detail-page">
    <div v-if="showHeader" class="window-header">
      <span class="header-back" @click="goBack">← 返回</span>
      <span class="header-breadcrumb">
        <span class="breadcrumb-item" @click="$router.push('/kb')">知识库</span>
        <span class="breadcrumb-sep">/</span>
        <template v-if="viewingDoc">
          <span class="breadcrumb-item" @click="viewingDoc = null">{{ kb?.name }}</span>
          <span class="breadcrumb-sep">/</span>
          <span class="breadcrumb-current">{{ viewingDoc.name }}</span>
        </template>
        <span v-else class="breadcrumb-current">{{ kb?.name }}</span>
      </span>
      <span v-if="!viewingDoc" class="header-tabs">
        <span class="htab" :class="{ active: tab === 'dataset' }" @click="tab = 'dataset'">文件列表</span>
        <span class="htab" :class="{ active: tab === 'testing' }" @click="tab = 'testing'">检索测试</span>
        <span class="htab" :class="{ active: tab === 'config' }" @click="tab = 'config'">配置</span>
      </span>
    </div>

    <div class="center-content center-content--table" v-show="tab === 'dataset' && !viewingDoc">
      <div class="docs-table-section">
        <div class="docs-toolbar">
          <h3>📁 文档文件 <span style="font-size:12px;color:#94a3b8;font-weight:400;">{{ docTotal }} 个</span></h3>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <el-button size="small" :loading="batchCleaning" @click="batchCleanAll">一键清洗</el-button>
            <el-button size="small" type="primary" :loading="batchChunking" @click="batchChunkAll">一键分块</el-button>
            <input ref="fileInput" type="file" multiple accept=".txt,.md,.pdf,.csv,.docx" style="display:none" @change="onUpload" />
            <el-button type="primary" size="small" :loading="uploading" @click="fileInput?.click()">上传文件</el-button>
            <el-button size="small" :loading="docsLoading" @click="loadDocs">刷新</el-button>
          </div>
        </div>
        <div class="docs-table-body">
          <el-table :data="docs" v-loading="docsLoading" stripe empty-text="请上传文档（txt / md / pdf / docx）">
          <el-table-column label="文件名" min-width="280">
            <template #default="{ row }">
              <span style="color:#2563eb;cursor:pointer;" @click="openDoc(row)">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="上传时间" width="170">
            <template #default="{ row }">{{ formatDate(row.create_date) }}</template>
          </el-table-column>
          <el-table-column label="启用" width="80" align="center">
            <template #default="{ row }">
              <el-switch :model-value="row.status === '1'" @change="toggleStatus(row)" />
            </template>
          </el-table-column>
          <el-table-column prop="chunk_count" label="分块数" width="70" align="center" />
          <el-table-column label="清洗状态" width="100" align="center">
            <template #default="{ row }">
              <span v-if="row.clean_run === 'RUNNING'" style="color:#ea580c;font-size:12px;">清洗中</span>
              <span v-else-if="row.clean_run === '1'" style="color:#16a34a;font-size:12px;">已清洗</span>
              <span v-else style="color:#94a3b8;font-size:12px;">待清洗</span>
            </template>
          </el-table-column>
          <el-table-column label="时效" width="110" align="center">
            <template #default="{ row }">
              <template v-if="row.timeliness?.level === 'warning' || row.timeliness?.level === 'info'">
                <el-popover placement="left" :width="400" trigger="click">
                  <template #reference>
                    <el-tooltip :content="timelinessHoverText(row)" placement="top" :show-after="250">
                      <el-tag
                        :type="row.timeliness.level === 'warning' ? 'danger' : 'info'"
                        size="small"
                        class="timeliness-tag"
                      >
                        {{ row.timeliness.level === 'warning' ? '疑似废止' : '有修订' }}
                      </el-tag>
                    </el-tooltip>
                  </template>
                  <div class="timeliness-detail">
                    <div class="timeliness-detail-title">{{ timelinessPopoverTitle(row) }}</div>
                    <div v-if="row.timeliness.warnings?.length" class="timeliness-detail-section">
                      <div class="timeliness-detail-label danger">
                        废止 / 失效相关（{{ row.timeliness.warnings.length }}）
                      </div>
                      <ul>
                        <li v-for="(item, idx) in row.timeliness.warnings" :key="'w-' + idx">{{ item }}</li>
                      </ul>
                    </div>
                    <div v-if="row.timeliness.hints?.length" class="timeliness-detail-section">
                      <div class="timeliness-detail-label info">
                        修订 / 施行相关（{{ row.timeliness.hints.length }}）
                      </div>
                      <ul>
                        <li v-for="(item, idx) in row.timeliness.hints" :key="'h-' + idx">{{ item }}</li>
                      </ul>
                    </div>
                    <div v-if="timelinessHasMore(row)" class="timeliness-detail-more">
                      全文共命中 {{ timelinessTotalCount(row) }} 处，以上仅展示前 {{ timelinessShownCount(row) }} 条
                    </div>
                  </div>
                </el-popover>
              </template>
              <span v-else style="color:#94a3b8;font-size:12px;">—</span>
            </template>
          </el-table-column>
          <el-table-column label="分块状态" width="100" align="center">
            <template #default="{ row }">
              <span v-if="row.run === 'RUNNING'" style="color:#ea580c;font-size:12px;">分块中</span>
              <span v-else-if="row.run === '1' && row.progress >= 1" style="color:#16a34a;font-size:12px;">已完成</span>
              <span v-else style="color:#94a3b8;font-size:12px;">待分块</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="320">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                size="small"
                :disabled="row.clean_run === 'RUNNING'"
                @click="cleanDoc(row)"
              >清洗</el-button>
              <el-button
                link
                type="primary"
                size="small"
                :disabled="row.clean_run !== '1' || row.run === 'RUNNING'"
                @click="chunkDoc(row)"
              >分块</el-button>
              <el-button link size="small" @click="renameDoc(row)">重命名</el-button>
              <el-button link size="small" @click="download(row)">下载</el-button>
              <el-button link type="danger" size="small" @click="delDoc(row)">删除</el-button>
            </template>
          </el-table-column>
          </el-table>
        </div>
        <div class="docs-table-footer">
          <el-pagination
            v-model:current-page="docPage"
            v-model:page-size="docPageSize"
            :total="docTotal"
            layout="total, prev, pager, next"
            @current-change="loadDocs"
            @size-change="() => { docPage = 1; loadDocs() }"
          />
        </div>
      </div>
    </div>

    <div v-if="viewingDoc" class="kb-doc-view">
      <div class="doc-panel" style="border-right:2px solid #f0f2f5;border-radius:14px 0 0 14px;">
        <div class="doc-panel-header">
          <span>📄 清洗后正文</span>
          <span style="font-size:11px;color:#94a3b8;">{{ viewingDoc.name }}</span>
        </div>
        <div class="doc-panel-body" v-loading="cleanedLoading">
          <el-alert
            v-if="viewingDoc?.timeliness?.warnings?.length || viewingDoc?.timeliness?.hints?.length"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom:12px;"
          >
            <template #title>
              <span>时效性检测</span>
              <el-popover placement="bottom" :width="400" trigger="click">
                <template #reference>
                  <el-button link type="primary" size="small" style="margin-left:8px;padding:0;">查看全部命中原因</el-button>
                </template>
                <div class="timeliness-detail">
                  <div class="timeliness-detail-title">{{ timelinessPopoverTitle(viewingDoc) }}</div>
                  <div v-if="viewingDoc.timeliness.warnings?.length" class="timeliness-detail-section">
                    <div class="timeliness-detail-label danger">
                      废止 / 失效相关（{{ viewingDoc.timeliness.warnings.length }}）
                    </div>
                    <ul>
                      <li v-for="(item, idx) in viewingDoc.timeliness.warnings" :key="'vw-' + idx">{{ item }}</li>
                    </ul>
                  </div>
                  <div v-if="viewingDoc.timeliness.hints?.length" class="timeliness-detail-section">
                    <div class="timeliness-detail-label info">
                      修订 / 施行相关（{{ viewingDoc.timeliness.hints.length }}）
                    </div>
                    <ul>
                      <li v-for="(item, idx) in viewingDoc.timeliness.hints" :key="'vh-' + idx">{{ item }}</li>
                    </ul>
                  </div>
                  <div v-if="timelinessHasMore(viewingDoc)" class="timeliness-detail-more">
                    全文共命中 {{ timelinessTotalCount(viewingDoc) }} 处，以上仅展示前 {{ timelinessShownCount(viewingDoc) }} 条
                  </div>
                </div>
              </el-popover>
            </template>
            <div>{{ timelinessHoverText(viewingDoc) }}</div>
          </el-alert>
          <pre style="white-space:pre-wrap;font-size:13px;line-height:1.7;margin:0;">{{ cleanedText || '（清洗后将显示清洗后的纯文本）' }}</pre>
        </div>
      </div>
      <div class="doc-panel" style="border-radius:0 14px 14px 0;">
        <div class="doc-panel-header">
          <span>✂️ 切片 <span style="font-size:11px;color:#94a3b8;font-weight:400;">{{ chunkTotal }} 条</span></span>
          <div style="display:flex;gap:8px;align-items:center;">
            <el-input
              v-model="chunkSearch"
              size="small"
              placeholder="搜索"
              clearable
              style="width:120px;"
              @keyup.enter="searchChunks"
              @clear="searchChunks"
            />
            <el-button v-if="selected.length" size="small" type="success" @click="batchAvail(true)">启用</el-button>
            <el-button v-if="selected.length" size="small" @click="batchAvail(false)">禁用</el-button>
            <el-button v-if="selected.length" size="small" type="danger" @click="batchDel">删除</el-button>
          </div>
        </div>
        <div class="doc-panel-body" v-loading="chunksLoading">
          <el-alert
            v-if="chunksNeedReparse"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom:12px;"
            title="当前切片为旧版 HTML 内容，请依次点击「清洗」与「分块」重新处理。"
          />
          <el-alert
            v-else-if="chunksLookMerged"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom:12px;"
            title="当前切片仍为旧版大块合并（结构化文档通常应有较多条目）。请重启后端后依次点击「清洗」「分块」，或删除重复文件只保留一条。"
          />
          <div v-for="(ch, idx) in chunks" :key="ch.id" class="chunk-card" :class="{ 'chunk-disabled': !ch.available }">
            <div style="display:flex;align-items:center;margin-bottom:8px;">
              <el-checkbox :model-value="selected.includes(ch.id)" @change="toggleSel(ch.id)" />
              <span style="margin-left:8px;font-size:11px;color:#2563eb;font-weight:700;">#{{ (chunkPage - 1) * chunkPageSize + idx + 1 }}</span>
              <div style="margin-left:auto;">
                <el-button link size="small" @click="toggleChunk(ch)">{{ ch.available ? '禁用' : '启用' }}</el-button>
                <el-button link type="danger" size="small" @click="delChunk(ch)">删除</el-button>
              </div>
            </div>
            <div style="font-size:13px;line-height:1.7;">{{ ch.content }}</div>
          </div>
          <div v-if="chunkTotal > chunkPageSize" style="margin-top:12px;display:flex;justify-content:flex-end;">
            <el-pagination
              v-model:current-page="chunkPage"
              :page-size="chunkPageSize"
              :total="chunkTotal"
              layout="total, prev, pager, next"
              small
              @current-change="loadChunks"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="center-content" v-show="tab === 'testing' && !viewingDoc">
      <div class="retrieval-hero">
        <h3 style="margin-bottom:6px;">🔍 知识检索测试</h3>
        <p style="font-size:13px;color:#94a3b8;margin-bottom:16px;">验证文档内容能否被正确召回</p>
        <div style="display:flex;gap:10px;">
          <el-input v-model="testQ" placeholder="例如：试用期最长多久？" @keyup.enter="doTest" />
          <span style="white-space:nowrap;font-size:12px;">Top-K</span>
          <el-input-number v-model="testK" :min="1" :max="20" size="small" />
          <el-button type="primary" :loading="testLoading" @click="doTest">检索</el-button>
        </div>
      </div>
      <div v-for="(r, i) in testResults" :key="i" class="retrieval-result-card">
        <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
          <span style="font-size:11px;color:#94a3b8;">{{ r.doc_name }}</span>
          <span style="font-weight:700;color:#2563eb;">{{ (r.similarity * 100).toFixed(1) }}%</span>
        </div>
        <div style="font-size:13px;line-height:1.7;">{{ r.content }}</div>
      </div>
      <div v-if="testDone && !testResults.length" style="text-align:center;padding:40px;color:#94a3b8;">未检索到相关内容</div>

      <div class="config-section" style="margin-top:24px;">
        <h4>批量检索测试</h4>
        <p style="font-size:12px;color:#64748b;margin-bottom:10px;">每行一个问题，用于对比召回效果</p>
        <el-input v-model="batchQuestions" type="textarea" :rows="6" placeholder="产品保修期是多久？&#10;退换货流程是什么？" />
        <div style="margin-top:10px;display:flex;gap:10px;">
          <el-button type="primary" :loading="batchLoading" @click="doBatchTest">批量检索</el-button>
          <el-button @click="rebuildIndex">重建向量索引</el-button>
        </div>
        <el-table v-if="batchResults.length" :data="batchResults" size="small" style="margin-top:16px;">
          <el-table-column prop="question" label="问题" min-width="200" />
          <el-table-column prop="hit_count" label="命中数" width="80" />
          <el-table-column label="最高相关度" width="110">
            <template #default="{ row }">{{ ((row.top_similarity || 0) * 100).toFixed(1) }}%</template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <div class="center-content" v-show="tab === 'config' && !viewingDoc">
      <div class="config-section">
        <h4>基本信息</h4>
        <el-form label-width="100px" size="small">
          <el-form-item label="名称"><el-input v-model="config.name" /></el-form-item>
          <el-form-item label="描述"><el-input v-model="config.description" type="textarea" :rows="2" /></el-form-item>
          <el-form-item label="权限">
            <el-select v-model="config.permission" style="width:100%">
              <el-option label="仅自己" value="me" />
              <el-option label="团队" value="team" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>
      <div class="config-section">
        <h4>清洗规则</h4>
        <p style="font-size:12px;color:#64748b;line-height:1.6;margin-bottom:12px;">
          上传后先清洗再切片：去页眉页脚/水印/目录噪声、剥离 HTML 样式、表格转结构化描述、去重复段落与已废止标记、统一全半角并清除乱码。
        </p>
        <el-form label-width="120px" size="small">
          <el-form-item label="启用清洗">
            <el-checkbox v-model="config.pc.clean_options.enabled">开启文本清洗</el-checkbox>
          </el-form-item>
          <el-form-item label="清洗规则">
            <el-checkbox-group v-model="cleanRuleKeys" :disabled="!config.pc.clean_options.enabled">
              <div class="clean-rule-grid">
                <el-checkbox label="remove_noise">去噪声（页眉页脚、水印、目录）</el-checkbox>
                <el-checkbox label="remove_format">去格式（剥离 HTML / 样式标签）</el-checkbox>
                <el-checkbox label="process_tables">表格处理（转为结构化描述）</el-checkbox>
                <el-checkbox label="remove_redundant">去冗余（重复段落、废止标记）</el-checkbox>
                <el-checkbox label="normalize_chars">字符规范化（全半角、乱码）</el-checkbox>
              </div>
            </el-checkbox-group>
          </el-form-item>
        </el-form>
      </div>
      <div class="config-section">
        <h4>切片设置</h4>
        <p style="font-size:12px;color:#64748b;line-height:1.6;margin-bottom:12px;">
          检测到「第一条」「第1章」等结构化标题时，将<strong>按条独立切片</strong>；单条过长时才按字数二次切分。自定义分隔符将覆盖自动规则。
        </p>
        <el-form label-width="100px" size="small">
          <el-form-item label="分块大小">
            <el-input-number v-model="config.pc.chunk_token_num" :min="64" :max="2048" :step="64" />
            <span style="font-size:11px;color:#94a3b8;margin-left:8px;">仅限制单条切片的最大长度</span>
          </el-form-item>
          <el-form-item label="分隔符">
            <el-input v-model="config.pc.delimiter" placeholder="留空则自动结构化切分；例如 \\n 按空行" />
          </el-form-item>
        </el-form>
        <div style="text-align:right;">
          <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { connectDatasetProgress } from '@/utils/datasetWs'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { formatDate } from '@/utils/format'
import { unwrapPage } from '@/utils/page'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const kbContext = inject('kbContext', null)

const datasetId = computed(() => route.params.id)
const kb = ref(null)
const tab = ref('dataset')
const viewingDoc = ref(null)
const docs = ref([])
const docPage = ref(1)
const docPageSize = ref(20)
const docTotal = ref(0)
const docsLoading = ref(false)
const uploading = ref(false)
const batchCleaning = ref(false)
const batchChunking = ref(false)
const fileInput = ref(null)
const chunks = ref([])
const chunkPage = ref(1)
const chunkPageSize = ref(50)
const chunkTotal = ref(0)
const chunksLoading = ref(false)
const chunkSearch = ref('')
const selected = ref([])
const saving = ref(false)

const testQ = ref('')
const testK = ref(5)
const testResults = ref([])
const testLoading = ref(false)
const testDone = ref(false)
const batchQuestions = ref('')
const batchResults = ref([])
const batchLoading = ref(false)

const DEFAULT_CLEAN_OPTIONS = {
  enabled: true,
  remove_noise: true,
  remove_format: true,
  process_tables: true,
  remove_redundant: true,
  normalize_chars: true,
}

const CLEAN_RULE_KEYS = ['remove_noise', 'remove_format', 'process_tables', 'remove_redundant', 'normalize_chars']

const config = reactive({
  name: '',
  description: '',
  permission: 'me',
  pc: {
    chunk_token_num: 512,
    delimiter: '',
    clean_options: { ...DEFAULT_CLEAN_OPTIONS },
  },
})

const cleanRuleKeys = computed({
  get() {
    const o = config.pc.clean_options
    return CLEAN_RULE_KEYS.filter((k) => o[k] !== false)
  },
  set(keys) {
    for (const k of CLEAN_RULE_KEYS) {
      config.pc.clean_options[k] = keys.includes(k)
    }
  },
})

const showHeader = computed(() => true)

const cleanedText = ref('')
const cleanedLoading = ref(false)
const chunksNeedReparse = computed(() =>
  chunks.value.some((c) => (c.content || '').includes('<') && (c.content || '').includes('style='))
)
const chunksLookMerged = computed(() => {
  if (!chunkTotal.value || !viewingDoc.value?.name) return false
  const name = viewingDoc.value.name
  if (!/第[一二三四五六七八九十\d]+条|第[一二三四五六七八九十\d]+章|\.md$/i.test(name)) return false
  const maxLen = chunks.value.length
    ? Math.max(...chunks.value.map((c) => (c.content || '').length))
    : 0
  const hasArticle = chunks.value.some((c) => /^第[一二三四五六七八九十百\d]+条/.test((c.content || '').trim()))
  return chunkTotal.value < 30 || (maxLen > 600 && !hasArticle)
})

const MAX_UPLOAD_MB = 50
const ALLOWED_EXTENSIONS = ['.txt', '.md', '.pdf', '.csv', '.docx']
let closeWs = null

function applyDocUpdate(payload) {
  if (!payload?.doc_id || !payload?.doc) return
  const idx = docs.value.findIndex((d) => d.id === payload.doc_id)
  if (idx >= 0) {
    docs.value[idx] = { ...docs.value[idx], ...payload.doc }
  }
  if (viewingDoc.value?.id === payload.doc_id) {
    viewingDoc.value = { ...viewingDoc.value, ...payload.doc }
  }
  if (payload.message) {
    if (payload.type === 'doc_error') ElMessage.error(payload.message)
    else if (payload.doc?.run === '1' || payload.doc?.clean_run === '1') ElMessage.success(payload.message)
    else ElMessage.info(payload.message)
  }
  if (payload.doc?.run === '1' && viewingDoc.value?.id === payload.doc_id) {
    loadChunks()
  }
}

function startDocWs() {
  closeWs?.()
  closeWs = connectDatasetProgress(datasetId.value, {
    onMessage: applyDocUpdate,
  })
}

watch(tab, (t) => kbContext?.setKbTab?.(t))
watch(viewingDoc, (d) => { if (kbContext) kbContext.viewingDoc = d })
watch(() => kb.value?.name, (n) => { if (kbContext) kbContext.kbName = n })

onMounted(async () => {
  try {
    const h = await api.getHealth()
    if (h?.chunking_version) {
      localStorage.setItem('chunking_version', h.chunking_version)
    }
  } catch {
    /* ignore */
  }
  await loadKb()
  await loadDocs()
  startDocWs()
})

onUnmounted(() => {
  closeWs?.()
})

async function loadKb() {
  const res = await api.getDatasets({ page: 1, page_size: 500 })
  const list = unwrapPage(res).items
  kb.value = list.find((d) => d.id === datasetId.value)
  if (!kb.value) {
    ElMessage.error('知识库不存在')
    router.push('/kb')
    return
  }
  config.name = kb.value.name
  config.description = kb.value.description || ''
  config.permission = kb.value.permission || 'me'
  const pc = kb.value.parser_config || {}
  config.pc.chunk_token_num = pc.chunk_token_num ?? 512
  config.pc.clean_options = { ...DEFAULT_CLEAN_OPTIONS, ...(pc.clean_options || {}) }
  config.pc.delimiter = pc.delimiter || ''
  if (kbContext) kbContext.kbName = kb.value.name
}

async function loadDocs() {
  docsLoading.value = true
  try {
    const res = await api.getDocuments(datasetId.value, {
      page: docPage.value,
      page_size: docPageSize.value,
    })
    const { items, total: t } = unwrapPage(res)
    docs.value = items
    docTotal.value = t
  } finally {
    docsLoading.value = false
  }
}

async function loadChunks() {
  if (!viewingDoc.value) return
  chunksLoading.value = true
  try {
    const params = {
      page: chunkPage.value,
      page_size: chunkPageSize.value,
    }
    const kw = chunkSearch.value.trim()
    if (kw) params.keyword = kw
    const res = await api.getChunks(datasetId.value, viewingDoc.value.id, params)
    const { items, total: t } = unwrapPage(res)
    chunks.value = items
    chunkTotal.value = t
  } finally {
    chunksLoading.value = false
  }
}

function searchChunks() {
  chunkPage.value = 1
  loadChunks()
}

async function batchCleanAll() {
  try {
    await ElMessageBox.confirm('将对本知识库全部文档启动清洗（进行中的将跳过），是否继续？', '一键清洗', { type: 'info' })
  } catch {
    return
  }
  batchCleaning.value = true
  try {
    const res = await api.batchProcessDocuments(datasetId.value, 'clean')
    ElMessage.success(res._message || '批量清洗已启动')
    await loadDocs()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    batchCleaning.value = false
  }
}

async function batchChunkAll() {
  try {
    await ElMessageBox.confirm('将对已清洗完成的文档启动分块（未清洗或进行中的将跳过），是否继续？', '一键分块', { type: 'info' })
  } catch {
    return
  }
  batchChunking.value = true
  try {
    const res = await api.batchProcessDocuments(datasetId.value, 'chunk')
    ElMessage.success(res._message || '批量分块已启动')
    await loadDocs()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    batchChunking.value = false
  }
}

function goBack() {
  if (viewingDoc.value) viewingDoc.value = null
  else router.push('/kb')
}

async function onUpload(e) {
  const files = e.target.files
  if (!files?.length) return
  for (const f of files) {
    const ext = (f.name.match(/\.[^.]+$/) || [''])[0].toLowerCase()
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      ElMessage.error(`「${f.name}」类型不支持，仅允许：${ALLOWED_EXTENSIONS.join(' ')}`)
      e.target.value = ''
      return
    }
    if (f.size > MAX_UPLOAD_MB * 1024 * 1024) {
      ElMessage.error(`「${f.name}」超过 ${MAX_UPLOAD_MB} MB 上限`)
      e.target.value = ''
      return
    }
  }
  uploading.value = true
  try {
    for (const f of files) {
      await api.uploadDocument(datasetId.value, f)
    }
    ElMessage.success('上传成功，请先点击「清洗」，再点击「分块」')
    await loadDocs()
    await store.fetchDatasets()
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    uploading.value = false
    e.target.value = ''
  }
}

async function cleanDoc(row) {
  row.clean_run = 'RUNNING'
  try {
    const updated = await api.updateDocument(datasetId.value, row.id, { clean: '1' })
    Object.assign(row, updated)
    ElMessage.info(updated._message || '清洗任务已启动')
  } catch (e) {
    row.clean_run = '0'
    ElMessage.error(e.message)
  }
}

async function chunkDoc(row) {
  if (row.clean_run !== '1') {
    ElMessage.warning('请先完成清洗后再分块')
    return
  }
  row.run = 'RUNNING'
  try {
    const updated = await api.updateDocument(datasetId.value, row.id, { run: '1' })
    Object.assign(row, updated)
    ElMessage.info(updated._message || '分块任务已启动')
  } catch (e) {
    row.run = '0'
    ElMessage.error(e.message)
  }
}

async function rebuildIndex() {
  try {
    const res = await api.rebuildIndex(datasetId.value)
    ElMessage.success(res._message || `索引已重建，共 ${res.indexed_chunks ?? res.count ?? 0} 条`)
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function doBatchTest() {
  const questions = batchQuestions.value.split('\n').map((s) => s.trim()).filter(Boolean)
  if (!questions.length) return ElMessage.warning('请输入至少一个问题')
  batchLoading.value = true
  try {
    const res = await api.batchRetrieval({
      dataset_ids: [datasetId.value],
      questions,
      top_k: testK.value,
    })
    batchResults.value = res.results || []
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    batchLoading.value = false
  }
}

async function toggleStatus(row) {
  const status = row.status === '1' ? '0' : '1'
  await api.updateDocument(datasetId.value, row.id, { status })
  row.status = status
}

async function renameDoc(row) {
  const { value } = await ElMessageBox.prompt('新文件名', '重命名', { inputValue: row.name })
  if (!value) return
  await api.updateDocument(datasetId.value, row.id, { name: value })
  await loadDocs()
}

async function download(row) {
  try {
    await api.downloadDocument(datasetId.value, row.id, row.name)
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

async function delDoc(row) {
  await ElMessageBox.confirm(`删除「${row.name}」？`, '确认', { type: 'warning' })
  await api.deleteDocuments(datasetId.value, [row.id])
  await loadDocs()
}

async function loadCleanedText(docId) {
  cleanedLoading.value = true
  try {
    const res = await api.getCleanedText(datasetId.value, docId)
    cleanedText.value = res.text || ''
  } catch {
    cleanedText.value = ''
  } finally {
    cleanedLoading.value = false
  }
}

async function openDoc(row) {
  viewingDoc.value = row
  tab.value = 'dataset'
  chunksLoading.value = true
  selected.value = []
  cleanedText.value = ''
  chunks.value = []
  chunkPage.value = 1
  chunkSearch.value = ''
  try {
    await loadCleanedText(row.id)
    await loadChunks()
  } finally {
    chunksLoading.value = false
  }
}

function toggleSel(id) {
  const i = selected.value.indexOf(id)
  if (i >= 0) selected.value.splice(i, 1)
  else selected.value.push(id)
}

async function toggleChunk(ch) {
  await api.updateChunk(datasetId.value, viewingDoc.value.id, ch.id, { available: !ch.available })
  ch.available = !ch.available
}

async function batchAvail(avail) {
  for (const id of selected.value) {
    await api.updateChunk(datasetId.value, viewingDoc.value.id, id, { available: avail })
    const ch = chunks.value.find((c) => c.id === id)
    if (ch) ch.available = avail
  }
  selected.value = []
}

async function batchDel() {
  await api.deleteChunks(datasetId.value, viewingDoc.value.id, selected.value)
  selected.value = []
  await loadChunks()
}

async function delChunk(ch) {
  await api.deleteChunks(datasetId.value, viewingDoc.value.id, [ch.id])
  await loadChunks()
}

async function doTest() {
  if (!testQ.value.trim()) return
  testLoading.value = true
  testDone.value = false
  try {
    const res = await api.retrieval({
      dataset_ids: [datasetId.value],
      question: testQ.value,
      top_k: testK.value,
    })
    testResults.value = res.chunks || []
    testDone.value = true
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    testLoading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    await api.updateDataset(datasetId.value, {
      name: config.name,
      description: config.description,
      permission: config.permission,
      parser_config: config.pc,
    })
    ElMessage.success('已保存')
    await loadKb()
    await store.fetchDatasets()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

watch(
  () => kbContext?.kbTab?.value,
  (t) => {
    if (t) tab.value = t
  }
)

function timelinessShownCount(row) {
  const t = row?.timeliness
  if (!t) return 0
  return (t.warnings?.length || 0) + (t.hints?.length || 0)
}

function timelinessTotalCount(row) {
  const t = row?.timeliness
  if (!t) return 0
  const total = (t.warning_count || 0) + (t.hint_count || 0)
  return total || timelinessShownCount(row)
}

function timelinessHasMore(row) {
  return timelinessTotalCount(row) > timelinessShownCount(row)
}

function timelinessPopoverTitle(row) {
  const label = row?.timeliness?.level === 'warning' ? '疑似废止' : '有修订'
  return `${row?.name || '文档'} · ${label}`
}

function timelinessHoverText(row) {
  const t = row?.timeliness
  if (!t) return ''
  const first = t.warnings?.[0] || t.hints?.[0] || ''
  const total = timelinessTotalCount(row)
  if (!first) return `共 ${total} 条命中原因，点击查看详情`
  const preview = first.length > 72 ? `${first.slice(0, 72)}…` : first
  return `${preview}（共 ${total} 条，点击查看全部）`
}
</script>

<style scoped>
.timeliness-tag {
  cursor: pointer;
}
.timeliness-detail {
  max-height: 320px;
  overflow-y: auto;
}
.timeliness-detail-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 10px;
  line-height: 1.5;
  word-break: break-word;
}
.timeliness-detail-section + .timeliness-detail-section {
  margin-top: 12px;
}
.timeliness-detail-label {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 6px;
}
.timeliness-detail-label.danger {
  color: #dc2626;
}
.timeliness-detail-label.info {
  color: #2563eb;
}
.timeliness-detail ul {
  margin: 0;
  padding-left: 18px;
}
.timeliness-detail li {
  font-size: 12px;
  line-height: 1.55;
  color: #475569;
  margin-bottom: 6px;
  word-break: break-word;
}
.timeliness-detail-more {
  margin-top: 10px;
  font-size: 11px;
  color: #94a3b8;
}
</style>
