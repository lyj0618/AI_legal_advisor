<template>
  <div>
    <div v-if="showHeader" class="window-header">
      <span class="header-back" @click="goBack">← 返回</span>
      <span class="header-breadcrumb">
        <span class="breadcrumb-item" @click="$router.push('/kb')">法律知识库</span>
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

    <div class="center-content" v-show="tab === 'dataset' && !viewingDoc">
      <div class="docs-table-section">
        <div class="docs-toolbar">
          <h3>📁 法规与制度文件 <span style="font-size:12px;color:#94a3b8;font-weight:400;">{{ docs.length }} 个</span></h3>
          <div>
            <input ref="fileInput" type="file" multiple accept=".txt,.md,.pdf,.csv,.docx" style="display:none" @change="onUpload" />
            <el-button type="primary" size="small" :loading="uploading" @click="fileInput?.click()">上传文件</el-button>
            <el-button size="small" :loading="docsLoading" @click="loadDocs">刷新</el-button>
          </div>
        </div>
        <el-table :data="docs" v-loading="docsLoading" stripe empty-text="请上传法律文档（txt / md / pdf / docx）">
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
    </div>

    <div v-if="viewingDoc" style="margin:-20px -28px -28px -20px;display:flex;height:calc(100vh - 50px);">
      <div class="doc-panel" style="border-right:2px solid #f0f2f5;border-radius:14px 0 0 14px;">
        <div class="doc-panel-header">
          <span>📄 清洗后正文</span>
          <span style="font-size:11px;color:#94a3b8;">{{ viewingDoc.name }}</span>
        </div>
        <div class="doc-panel-body" v-loading="cleanedLoading">
          <pre style="white-space:pre-wrap;font-size:13px;line-height:1.7;margin:0;">{{ cleanedText || '（清洗后将显示清洗后的纯文本）' }}</pre>
        </div>
      </div>
      <div class="doc-panel" style="border-radius:0 14px 14px 0;">
        <div class="doc-panel-header">
          <span>✂️ 切片 <span style="font-size:11px;color:#94a3b8;font-weight:400;">{{ chunks.length }} 条</span></span>
          <div style="display:flex;gap:8px;align-items:center;">
            <el-input v-model="chunkSearch" size="small" placeholder="搜索" clearable style="width:120px;" />
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
            title="当前切片仍为旧版大块合并（法条类文档通常应有几十至上千条）。请重启后端后依次点击「清洗」「分块」，或删除重复文件只保留一条。"
          />
          <div v-for="(ch, idx) in filteredChunks" :key="ch.id" class="chunk-card" :class="{ 'chunk-disabled': !ch.available }">
            <div style="display:flex;align-items:center;margin-bottom:8px;">
              <el-checkbox :model-value="selected.includes(ch.id)" @change="toggleSel(ch.id)" />
              <span style="margin-left:8px;font-size:11px;color:#2563eb;font-weight:700;">#{{ idx + 1 }}</span>
              <div style="margin-left:auto;">
                <el-button link size="small" @click="toggleChunk(ch)">{{ ch.available ? '禁用' : '启用' }}</el-button>
                <el-button link type="danger" size="small" @click="delChunk(ch)">删除</el-button>
              </div>
            </div>
            <div style="font-size:13px;line-height:1.7;">{{ ch.content }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="center-content" v-show="tab === 'testing' && !viewingDoc">
      <div class="retrieval-hero">
        <h3 style="margin-bottom:6px;">🔍 法律知识检索测试</h3>
        <p style="font-size:13px;color:#94a3b8;margin-bottom:16px;">验证法条、制度能否被正确召回</p>
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
          检测到「第一条」「第二条」等法条标题时，将<strong>按条独立切片</strong>（不再合并多条）；单条过长时才按字数二次切分。自定义分隔符将覆盖法条规则。
        </p>
        <el-form label-width="100px" size="small">
          <el-form-item label="分块大小">
            <el-input-number v-model="config.pc.chunk_token_num" :min="64" :max="2048" :step="64" />
            <span style="font-size:11px;color:#94a3b8;margin-left:8px;">仅限制单条法条的最大长度</span>
          </el-form-item>
          <el-form-item label="分隔符">
            <el-input v-model="config.pc.delimiter" placeholder="留空则自动按法条切分；例如 \\n 按空行" />
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
import { computed, inject, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { formatDate } from '@/utils/format'
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
const docsLoading = ref(false)
const uploading = ref(false)
const fileInput = ref(null)
const chunks = ref([])
const chunksLoading = ref(false)
const chunkSearch = ref('')
const selected = ref([])
const saving = ref(false)

const testQ = ref('')
const testK = ref(5)
const testResults = ref([])
const testLoading = ref(false)
const testDone = ref(false)

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
  if (!chunks.value.length || !viewingDoc.value?.name) return false
  const name = viewingDoc.value.name
  if (!/劳动合同法|民法典|\.md$/i.test(name)) return false
  const maxLen = Math.max(...chunks.value.map((c) => (c.content || '').length))
  const hasArticle = chunks.value.some((c) => /^第[一二三四五六七八九十百\d]+条/.test((c.content || '').trim()))
  return chunks.value.length < 30 || (maxLen > 600 && !hasArticle)
})
const filteredChunks = computed(() => {
  const q = chunkSearch.value.toLowerCase()
  return chunks.value.filter((c) => !q || (c.content || '').toLowerCase().includes(q))
})

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
})

async function loadKb() {
  const list = await api.getDatasets()
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
    const res = await api.getDocuments(datasetId.value)
    docs.value = res.docs || []
  } finally {
    docsLoading.value = false
  }
}

function goBack() {
  if (viewingDoc.value) viewingDoc.value = null
  else router.push('/kb')
}

async function onUpload(e) {
  const files = e.target.files
  if (!files?.length) return
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
  ElMessage.info('清洗中，请稍后')
  try {
    const updated = await api.updateDocument(datasetId.value, row.id, { clean: '1' })
    Object.assign(row, updated)
    ElMessage.success('已完成清洗')
    if (viewingDoc.value?.id === row.id) {
      await loadCleanedText(row.id)
    }
    await loadDocs()
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
  ElMessage.info('解析中，请稍后')
  try {
    const updated = await api.updateDocument(datasetId.value, row.id, { run: '1' })
    Object.assign(row, updated)
    const msg = updated?._message || updated?.message
    if (msg && String(msg).includes('嵌入失败')) {
      ElMessage.warning(msg)
    } else {
      if (updated?.chunk_count && updated.chunk_count < 20 && row.clean_run === '1') {
      ElMessage.warning(`仅生成 ${updated.chunk_count} 条切片，法条类文档通常应有数十条。请重启后端后重新点击「分块」。`)
    } else {
      ElMessage.success(msg && String(msg).includes('共') ? msg : '已完成解析')
    }
    }
    await loadDocs()
    if (viewingDoc.value?.id === row.id) {
      chunksLoading.value = true
      try {
        const res = await api.getChunks(datasetId.value, row.id)
        chunks.value = res.chunks || []
      } finally {
        chunksLoading.value = false
      }
    }
  } catch (e) {
    row.run = '0'
    ElMessage.error(e.message)
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

function download(row) {
  window.open(api.downloadDocument(datasetId.value, row.id), '_blank')
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
  try {
    await loadCleanedText(row.id)
    const res = await api.getChunks(datasetId.value, row.id)
    chunks.value = res.chunks || []
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
  chunks.value = chunks.value.filter((c) => !selected.value.includes(c.id))
  selected.value = []
}

async function delChunk(ch) {
  await api.deleteChunks(datasetId.value, viewingDoc.value.id, [ch.id])
  chunks.value = chunks.value.filter((c) => c.id !== ch.id)
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
</script>
