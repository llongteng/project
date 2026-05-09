"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchKnowledge,
  createKnowledge,
  updateKnowledge,
  deleteKnowledge,
} from "@/lib/api";
import { KBEntry } from "@/lib/types";
import { CATEGORY_LABELS } from "@/lib/constants";

export default function KnowledgePage() {
  const [entries, setEntries] = useState<KBEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<KBEntry | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchKnowledge({
        search: search || undefined,
        category: categoryFilter || undefined,
      });
      setEntries(data);
    } catch {
      setError("加载失败");
    } finally {
      setLoading(false);
    }
  }, [search, categoryFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const handleToggle = async (entry: KBEntry) => {
    try {
      await updateKnowledge(entry.id, { enabled: !entry.enabled });
      await load();
    } catch {
      alert("操作失败");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确定删除该知识条目？")) return;
    try {
      await deleteKnowledge(id);
      await load();
    } catch {
      alert("删除失败");
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">知识库管理</h1>
        <button
          onClick={() => {
            setEditing(null);
            setShowForm(true);
          }}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          新增条目
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索关键词..."
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-64"
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
        >
          <option value="">全部分类</option>
          {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
          {error}
        </div>
      )}

      {loading && <p className="text-gray-500 text-center py-12">加载中...</p>}

      {!loading && entries.length === 0 && (
        <p className="text-gray-500 text-center py-12">暂无知识条目</p>
      )}

      {!loading && entries.length > 0 && (
        <div className="space-y-2">
          {entries.map((e) => (
            <div
              key={e.id}
              className={`bg-white border rounded-lg p-4 ${
                e.enabled ? "border-gray-200" : "border-gray-100 opacity-60"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-gray-900">{e.title}</h3>
                    <span className="text-xs text-gray-400">
                      {CATEGORY_LABELS[e.category] || e.category}
                    </span>
                    {!e.enabled && (
                      <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                        已停用
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                    {e.content}
                  </p>
                  {e.keywords && (
                    <div className="flex gap-1 mt-1 flex-wrap">
                      {e.keywords.split(",").map((kw) => (
                        <span
                          key={kw}
                          className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded"
                        >
                          {kw.trim()}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => handleToggle(e)}
                    className={`px-2 py-1 text-xs rounded border ${
                      e.enabled
                        ? "border-gray-200 text-gray-600 hover:bg-gray-100"
                        : "border-green-200 text-green-600 hover:bg-green-50"
                    }`}
                  >
                    {e.enabled ? "停用" : "启用"}
                  </button>
                  <button
                    onClick={() => {
                      setEditing(e);
                      setShowForm(true);
                    }}
                    className="px-2 py-1 text-xs rounded border border-gray-200 text-gray-600 hover:bg-gray-100"
                  >
                    编辑
                  </button>
                  <button
                    onClick={() => handleDelete(e.id)}
                    className="px-2 py-1 text-xs rounded border border-red-200 text-red-600 hover:bg-red-50"
                  >
                    删除
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <KBFormModal
          entry={editing}
          onClose={() => setShowForm(false)}
          onSaved={() => {
            setShowForm(false);
            setEditing(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function KBFormModal({
  entry,
  onClose,
  onSaved,
}: {
  entry: KBEntry | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!entry;
  const [title, setTitle] = useState(entry?.title || "");
  const [category, setCategory] = useState(entry?.category || "other");
  const [content, setContent] = useState(entry?.content || "");
  const [keywords, setKeywords] = useState(entry?.keywords || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !content) {
      setError("标题和内容为必填项");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (isEdit) {
        await updateKnowledge(entry!.id, { title, category, content, keywords });
      } else {
        await createKnowledge({ title, category, content, keywords });
      }
      onSaved();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4">
          {isEdit ? "编辑知识条目" : "新增知识条目"}
        </h2>
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm mb-4">
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              标题 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="知识条目标题"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              分类
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            >
              {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              内容 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={4}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="知识条目正文"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              关键词（逗号分隔）
            </label>
            <input
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="物流,订单,发货,查询"
            />
          </div>
          <div className="flex gap-2 justify-end pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "保存中..." : "保存"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
