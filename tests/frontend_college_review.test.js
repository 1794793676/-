"use strict";
/* US04 界面动作回归：用 Node vm 加载真实 app.js，桩替换 DOM / fetch，
 * 验证学院复核表单的渲染条件与请求端点，并确认辅导员初审表单未被改坏。
 * 零第三方依赖： node tests/frontend_college_review.test.js
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const APP = path.join(__dirname, "..", "scholarship", "static", "app.js");
const source = fs.readFileSync(APP, "utf8");
const APP_ID = "APP-TEST";

function application(status) {
  return {
    id: APP_ID, status, duplicate: false, student_name: "林同学（演示）",
    batch: "2026秋季第一批", submitted_at: "2026-10-19T08:00:00+00:00",
    fields: { phone: "13800000000", application_reason: "学业支持" },
    attachments: [], rejection_reason: "",
  };
}

function harness(status) {
  const calls = [], handlers = {}, elements = {};
  function el(name) {
    if (elements[name]) return elements[name];
    const e = {
      _html: "",
      classList: { add() {}, remove() {}, toggle() {} },
      addEventListener(type, fn) { handlers[name + ":" + type] = fn; },
      querySelectorAll() { return []; },
      scrollIntoView() {},
      textContent: "", className: "", disabled: false, value: "", files: [], dataset: {}, style: {},
    };
    Object.defineProperty(e, "innerHTML", {
      get() { return e._html; },
      set(value) { e._html = value; },
    });
    elements[name] = e;
    return e;
  }
  const document = { getElementById: el, querySelectorAll() { return []; } };
  const window = { scrollTo() {} };
  class FileReader {
    readAsDataURL() { this.result = "data:application/pdf;base64,JVBERi0="; this.onload(); }
  }
  async function fetch(pathname, options) {
    if (pathname === "/api/session") throw new Error("boot skipped in harness");
    const method = options && options.method;
    const body = options && options.body ? JSON.parse(options.body) : null;
    calls.push({ path: pathname, method, body });
    if (pathname === "/api/applications" && method !== "POST") {
      return { json: async () => ({ ok: true, data: [] }) };
    }
    if (pathname.slice(-6) === "/audit") {
      return { json: async () => ({ ok: true, data: [] }) };
    }
    if (pathname.indexOf("/api/applications/") === 0 && method !== "POST") {
      return { json: async () => ({ ok: true, data: application(status) }) };
    }
    return { json: async () => ({ ok: true, data: application("待公示") }) };
  }
  const ctx = { document, window, FileReader, fetch, console, setTimeout, clearTimeout };
  const hook = `
globalThis.__test = {
  openApplication,
  setSession: v => { session = v; },
};
`;
  vm.runInNewContext(source + "\n" + hook, ctx, { filename: "app.js" });
  return { ctx, calls, handlers, elements };
}

async function scenario(role, status) {
  const env = harness(status);
  env.ctx.__test.setSession({
    user: { id: "tester", name: "演示", role, college: "计算机学院" },
    csrf_token: "test-csrf-token",
  });
  await env.ctx.__test.openApplication(APP_ID);
  return env;
}

function submitEvent(decision) {
  return {
    preventDefault() {},
    submitter: { value: decision },
    target: { querySelectorAll() { return []; } },
  };
}

async function testCollegeReviewFormUsesNewEndpoint() {
  const env = await scenario("college_reviewer", "待学院复核");
  const html = env.elements["applicationDetail"].innerHTML;
  assert.ok(html.indexOf("通过学院复核") >= 0, "学院审核员应看到通过学院复核按钮");
  assert.ok(html.indexOf("通过初审") < 0, "不应显示辅导员初审按钮文案");
  assert.ok(env.handlers["reviewForm:submit"], "应绑定复核表单的提交处理器");
  await env.handlers["reviewForm:submit"](submitEvent("approve"));
  const post = env.calls.find(c => c.method === "POST");
  assert.ok(post, "应发起复核请求");
  assert.strictEqual(post.path, "/api/applications/" + APP_ID + "/college-review");
  assert.strictEqual(post.body.decision, "approve");
  console.log("PASS 01 学院复核表单渲染并调用 /college-review");
}

async function testCounselorFormKeepsOriginalEndpoint() {
  const env = await scenario("counselor", "待辅导员审核");
  const html = env.elements["applicationDetail"].innerHTML;
  assert.ok(html.indexOf("通过初审") >= 0, "辅导员应看到通过初审按钮");
  assert.ok(html.indexOf("通过学院复核") < 0, "不应显示学院复核按钮文案");
  assert.ok(env.handlers["reviewForm:submit"], "应绑定初审表单的提交处理器");
  await env.handlers["reviewForm:submit"](submitEvent("approve"));
  const post = env.calls.find(c => c.method === "POST");
  assert.strictEqual(post.path, "/api/applications/" + APP_ID + "/review");
  console.log("PASS 02 辅导员初审表单仍调用原有 /review");
}

async function testNoReviewFormAfterCollegeApproval() {
  const env = await scenario("college_reviewer", "待公示");
  const html = env.elements["applicationDetail"].innerHTML;
  assert.ok(html.indexOf("等待学生处公示") >= 0, "待公示状态应给出公示不是最终结果的说明");
  assert.ok(!env.handlers["reviewForm:submit"], "待公示状态不应再渲染复核表单");
  console.log("PASS 03 待公示状态不再渲染复核表单");
}

(async () => {
  try {
    await testCollegeReviewFormUsesNewEndpoint();
    await testCounselorFormKeepsOriginalEndpoint();
    await testNoReviewFormAfterCollegeApproval();
    console.log("FRONTEND US04: 3 PASS, 0 FAIL");
  } catch (error) {
    console.error("FRONTEND US04 FAILED: " + error.message);
    process.exitCode = 1;
  }
})();
