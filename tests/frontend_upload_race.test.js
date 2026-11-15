"use strict";
/* Regression for the PR #1 review finding:
 * "Capture the project before starting asynchronous uploads".
 *
 * This harness runs the REAL scholarship/static/app.js inside a Node vm with a
 * stubbed DOM / FileReader / fetch, then replays the race: while the first
 * attachment upload is in flight, the student opens another notification.
 * No third-party package is needed:  node tests/frontend_upload_race.test.js
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const APP = path.join(__dirname, "..", "scholarship", "static", "app.js");
const source = fs.readFileSync(APP, "utf8");

const PROJECT_OPEN = {
  id: "open", name: "2026秋季学业奖学金", batch: "2026秋季第一批",
  conditions: "全日制在校生", open_at: "2026-10-01T00:00:00+00:00",
  deadline: "2026-12-31T00:00:00+00:00", window_state: "开放中", can_apply: true,
  required_fields: [{ key: "phone", label: "联系电话" }, { key: "application_reason", label: "申请理由" }],
  required_materials: [{ key: "transcript", label: "成绩单" }, { key: "proof", label: "证明材料" }],
};
const PROJECT_OTHER = Object.assign({}, PROJECT_OPEN, {
  id: "future", name: "另一个通知", window_state: "未开始", can_apply: false,
});
const SESSION = {
  user: { id: "student1", name: "林同学（演示）", role: "student", college: "计算机学院" },
  csrf_token: "test-csrf-token",
};
const APPLICATION = {
  id: "APP-TEST", status: "待辅导员审核", duplicate: false,
  fields: { phone: "13800000000", application_reason: "学业支持" },
  attachments: [], submitted_at: "2026-10-19T08:00:00+00:00", rejection_reason: "",
};

function makeElement() {
  return {
    classList: { add() {}, remove() {}, toggle() {} },
    addEventListener() {}, removeEventListener() {},
    querySelectorAll() { return []; },
    scrollIntoView() {},
    textContent: "", innerHTML: "", className: "", disabled: false,
    value: "", files: [], dataset: {}, style: {},
    elements: { namedItem() { return { value: "13800000000" }; } },
  };
}

function harness(options) {
  const calls = [];
  const elements = {};
  const $ = id => (elements[id] || (elements[id] = makeElement()));
  let uploadCount = 0;
  const form = {
    querySelectorAll(selector) {
      if (selector !== "[data-material]") return [];
      return [
        { dataset: { material: "transcript" }, files: [{ name: "transcript.pdf", size: 32 }] },
        { dataset: { material: "proof" }, files: [{ name: "proof.pdf", size: 32 }] },
      ];
    },
    elements: { namedItem() { return { value: "13800000000" }; } },
  };
  const document = { getElementById: $, querySelectorAll() { return []; } };
  const window = { scrollTo() {} };
  class FileReader {
    readAsDataURL() { this.result = "data:application/pdf;base64,JVBERi0="; this.onload(); }
  }
  async function fetch(pathname, requestOptions) {
    if (pathname === "/api/session") throw new Error("boot skipped in harness");
    const body = requestOptions && requestOptions.body ? JSON.parse(requestOptions.body) : null;
    calls.push({ path: pathname, method: requestOptions && requestOptions.method, body });
    if (pathname === "/api/uploads") {
      uploadCount += 1;
      if (options.switchDuringUpload && uploadCount === 1) {
        // Student clicks another notification while the first upload is pending.
        ctx.__test.setProject(PROJECT_OTHER);
      }
      if (options.openProjectDuringUpload && uploadCount === 1) {
        await ctx.__test.openProject("future");
      }
      return { json: async () => ({ ok: true, data: { id: "att-" + uploadCount } }) };
    }
    if (pathname.indexOf("/api/projects/") === 0) {
      return { json: async () => ({ ok: true, data: PROJECT_OTHER }) };
    }
    if (pathname === "/api/applications" && requestOptions.method === "POST") {
      return { json: async () => ({ ok: true, data: APPLICATION }) };
    }
    if (pathname === "/api/applications") {
      return { json: async () => ({ ok: true, data: [] }) };
    }
    if (pathname.slice(-6) === "/audit") {
      return { json: async () => ({ ok: true, data: [] }) };
    }
    return { json: async () => ({ ok: true, data: APPLICATION }) };
  }
  const ctx = { document, window, FileReader, fetch, console, setTimeout, clearTimeout };
  const hook = `
globalThis.__test = {
  submitApplication, openProject,
  setProject: v => { selectedProject = v; },
  getProject: () => selectedProject,
  setSession: v => { session = v; },
};
`;
  vm.runInNewContext(source + "\n" + hook, ctx, { filename: "app.js" });
  return { ctx, calls, form };
}

async function testSnapshotSurvivesProjectSwitch() {
  const { ctx, calls, form } = harness({ switchDuringUpload: true });
  ctx.__test.setSession(SESSION);
  ctx.__test.setProject(PROJECT_OPEN);
  await ctx.__test.submitApplication({ preventDefault() {}, target: form });
  const uploads = calls.filter(c => c.path === "/api/uploads");
  const submitted = calls.find(c => c.path === "/api/applications" && c.body && c.body.attachment_ids);
  assert.strictEqual(uploads.length, 2, "两个材料都应发起上传请求");
  assert.ok(submitted, "应发出最终申请请求");
  assert.deepStrictEqual(uploads.map(c => c.body.project_id), ["open", "open"],
    "上传中的每次请求都必须使用提交开始时锁定的项目");
  assert.strictEqual(submitted.body.project_id, "open",
    "最终申请必须提交到提交开始时锁定的项目，而不是后来打开的通知");
  console.log("PASS 01 提交快照：上传期间切换通知，附件与申请仍属于原项目");
}

async function testNavigationLockedWhileSending() {
  const { ctx, form } = harness({ openProjectDuringUpload: true });
  ctx.__test.setSession(SESSION);
  ctx.__test.setProject(PROJECT_OPEN);
  await ctx.__test.submitApplication({ preventDefault() {}, target: form });
  assert.strictEqual(ctx.__test.getProject().id, "open",
    "提交进行中不允许切换通知，selectedProject 应保持原项目");
  console.log("PASS 02 导航锁定：提交期间点击其他通知不会改变当前项目");
}

(async () => {
  try {
    await testSnapshotSurvivesProjectSwitch();
    await testNavigationLockedWhileSending();
    console.log("FRONTEND RACE: 2 PASS, 0 FAIL");
  } catch (error) {
    console.error("FRONTEND RACE FAILED: " + error.message);
    process.exitCode = 1;
  }
})();
