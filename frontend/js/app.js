const API = 'http://localhost:8080/api';

const STATUS_LABELS = {
    PENDING_COUNSELOR: '待辅导员审核',
    PENDING_COLLEGE: '待学院复核',
    PENDING_PUBLICITY: '待公示',
    PUBLICIZING: '公示中',
    APPROVED: '已获批',
    REJECTED_UNSELECTED: '未获批',
    REJECTED: '已驳回',
    RETURNED: '待补正',
    CORRECTION_EXPIRED: '补正逾期'
};

const SHORT_LABELS = {
    PENDING_COUNSELOR: '待辅导员',
    PENDING_COLLEGE: '待学院',
    PENDING_PUBLICITY: '待公示',
    PUBLICIZING: '公示中',
    APPROVED: '已获批',
    REJECTED_UNSELECTED: '未获批',
    REJECTED: '已驳回',
    RETURNED: '待补正',
    CORRECTION_EXPIRED: '补正逾期'
};

const ROLE_LABELS = {
    STUDENT: '学生',
    COUNSELOR: '辅导员',
    COLLEGE: '学院审核员',
    AFFAIRS: '学生处'
};

const ROLE_TABS = {
    STUDENT: [
        {key: 'notices', label: '通知公告'},
        {key: 'myapps', label: '我的申请'},
        {key: 'publicity', label: '公示名单'}
    ],
    COUNSELOR: [{key: 'counselor', label: '学生申请审核'}],
    COLLEGE: [{key: 'college', label: '学院复核'}],
    AFFAIRS: [
        {key: 'affairs', label: '公示管理'},
        {key: 'stats', label: '统计分析'}
    ]
};

function fmt(value) {
    if (!value) {
        return '-';
    }
    return String(value).replace('T', ' ').slice(0, 16);
}

function toLocalInput(date) {
    const pad = n => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
        + `T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function statusClass(status) {
    const map = {
        PENDING_COUNSELOR: 'amber',
        PENDING_COLLEGE: 'amber',
        PENDING_PUBLICITY: 'amber',
        PUBLICIZING: 'blue',
        APPROVED: 'green',
        REJECTED_UNSELECTED: 'red',
        REJECTED: 'red',
        RETURNED: 'orange',
        CORRECTION_EXPIRED: 'gray'
    };
    return map[status] || 'gray';
}

function statusClassByLabel(label) {
    const map = {'公示中': 'blue', '已获批': 'green', '未获批': 'red'};
    return map[label] || 'gray';
}

async function apiRequest(method, path, body = null, withAuth = true) {
    const headers = {'Content-Type': 'application/json'};
    const user = JSON.parse(localStorage.getItem('user') || 'null');
    if (withAuth && user) {
        headers['X-Session-Token'] = user.token;
    }
    const res = await fetch(API + path, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined
    });
    const text = await res.text();
    let data = null;
    if (text) {
        try {
            data = JSON.parse(text);
        } catch {
            data = null;
        }
    }
    if (!res.ok) {
        if (res.status === 401 && withAuth) {
            localStorage.removeItem('user');
        }
        throw new Error((data && data.message) || ('请求失败（' + res.status + '）'));
    }
    return data;
}

const ApplicationDetail = {
    props: ['app'],
    methods: {fmt, statusClass},
    template: `
        <div class="app-detail">
            <div class="row-between">
                <div>
                    <h3>{{ app.projectName }} · {{ app.batchName }}</h3>
                    <p class="muted small">申请编号：{{ app.applyNo }}</p>
                </div>
                <span :class="['tag', statusClass(app.status)]">{{ app.statusLabel }}</span>
            </div>
            <div class="kv-grid">
                <div><span>申请人</span><b>{{ app.studentName }}（{{ app.studentNo }}）</b></div>
                <div><span>学院</span><b>{{ app.college }}</b></div>
                <div><span>拟获等级</span><b>{{ app.level }}</b></div>
                <div><span>提交时间</span><b>{{ fmt(app.submitTime) }}</b></div>
            </div>
            <div class="block">
                <h4>申请理由</h4>
                <p>{{ app.reason }}</p>
            </div>
            <div class="block">
                <h4>已交材料</h4>
                <p>{{ app.materials.join('、') || '无' }}</p>
                <p v-if="app.prevMaterials && app.prevMaterials.length" class="muted small">
                    补正前材料：{{ app.prevMaterials.join('、') }}
                </p>
            </div>
            <div class="block" v-if="app.counselorOpinion || app.counselorReviewedAt">
                <h4>辅导员审核</h4>
                <p>{{ app.counselorOpinion || '（无意见）' }}
                    <span v-if="app.counselorReviewedAt" class="muted small"> · {{ fmt(app.counselorReviewedAt) }}</span>
                </p>
            </div>
            <div class="block" v-if="app.collegeOpinion || app.collegeReviewedAt">
                <h4>学院复核</h4>
                <p>{{ app.collegeOpinion || '（无意见）' }}
                    <span v-if="app.collegeReviewedAt" class="muted small"> · {{ fmt(app.collegeReviewedAt) }}</span>
                </p>
            </div>
            <div class="block" v-if="app.correctionOpinion">
                <h4>补正意见</h4>
                <p>{{ app.correctionOpinion }}
                    <span class="muted small"> · 截止 {{ fmt(app.correctionDeadline) }}</span>
                </p>
            </div>
            <div class="block" v-if="app.finalReason">
                <h4>最终结果说明</h4>
                <p>{{ app.finalReason }}</p>
            </div>
            <div class="block" v-if="app.confirmedAt">
                <h4>最终确认</h4>
                <p>{{ app.statusLabel }}<span class="muted small"> · {{ fmt(app.confirmedAt) }}</span></p>
            </div>
        </div>
    `
};

const app = Vue.createApp({
    data() {
        return {
            currentUser: JSON.parse(localStorage.getItem('user') || 'null'),
            view: '',
            loginForm: {username: '', password: ''},
            error: '',
            success: '',
            errorTimer: null,
            successTimer: null,

            notices: [],
            selectedNotice: null,
            applyForm: {reason: '', materials: []},

            myApps: [],
            selectedApp: null,
            resubmitForm: {reason: '', materials: []},

            counselorApps: [],
            counselorFilter: 'PENDING',
            collegeApps: [],
            collegeFilter: 'PENDING',
            reviewForm: {comment: '', opinion: '', deadline: ''},

            publicNoticeId: null,
            publicData: null,

            affairsNoticeId: null,
            candidates: [],
            publishIds: [],
            publishStart: '',
            publishEnd: '',
            adminNoticeId: null,
            adminData: null,
            disputeHandled: false,
            confirmItems: {},

            statsNoticeId: null,
            statsCollege: '',
            stats: null,
            statusList: Object.keys(STATUS_LABELS)
        };
    },

    computed: {
        tabs() {
            return this.currentUser ? (ROLE_TABS[this.currentUser.role] || []) : [];
        },
        myAppForSelected() {
            if (!this.selectedNotice) {
                return null;
            }
            return this.myApps.find(a => a.noticeId === this.selectedNotice.id) || null;
        },
        publicizedNotices() {
            return this.notices.filter(n => n.publicized);
        },
        filteredCounselorApps() {
            if (this.counselorFilter === 'PENDING') {
                return this.counselorApps.filter(a => a.status === 'PENDING_COUNSELOR');
            }
            return this.counselorApps;
        },
        filteredCollegeApps() {
            if (this.collegeFilter === 'PENDING') {
                return this.collegeApps.filter(a => a.status === 'PENDING_COLLEGE');
            }
            return this.collegeApps;
        },
        adminPublicizing() {
            return this.adminData ? this.adminData.list.filter(a => a.status === 'PUBLICIZING') : [];
        }
    },

    methods: {
        fmt,
        statusClass,
        statusClassByLabel,
        shortLabel(status) {
            return SHORT_LABELS[status] || status;
        },
        roleLabel(role) {
            return ROLE_LABELS[role] || role;
        },
        notifySuccess(message) {
            this.success = message;
            clearTimeout(this.successTimer);
            this.successTimer = setTimeout(() => {
                this.success = '';
            }, 5000);
        },
        notifyError(message) {
            this.error = message;
            clearTimeout(this.errorTimer);
            this.errorTimer = setTimeout(() => {
                this.error = '';
            }, 5000);
        },
        defaultView() {
            const tabs = ROLE_TABS[this.currentUser.role] || [];
            return tabs.length ? tabs[0].key : '';
        },
        async login() {
            try {
                const user = await apiRequest('POST', '/auth/login', this.loginForm, false);
                this.currentUser = user;
                localStorage.setItem('user', JSON.stringify(user));
                this.loginForm.password = '';
                this.error = '';
                await this.afterLogin();
            } catch (e) {
                this.notifyError(e.message);
            }
        },
        quickLogin(username) {
            this.loginForm.username = username;
            this.loginForm.password = '123456';
            this.login();
        },
        logout() {
            localStorage.removeItem('user');
            this.currentUser = null;
            this.view = '';
            this.notices = [];
            this.selectedNotice = null;
            this.selectedApp = null;
            this.myApps = [];
            this.counselorApps = [];
            this.collegeApps = [];
            this.publicData = null;
            this.candidates = [];
            this.adminData = null;
            this.stats = null;
            this.error = '';
            this.success = '';
        },
        async afterLogin() {
            this.view = this.defaultView();
            try {
                await this.loadNotices();
                if (this.currentUser.role === 'STUDENT') {
                    await this.loadMyApps();
                    this.initPublicity();
                } else if (this.currentUser.role === 'COUNSELOR') {
                    await this.loadCounselor();
                } else if (this.currentUser.role === 'COLLEGE') {
                    await this.loadCollege();
                } else if (this.currentUser.role === 'AFFAIRS') {
                    await this.initAffairs();
                }
            } catch (e) {
                this.notifyError(e.message);
            }
        },
        async switchView(key) {
            this.view = key;
            this.error = '';
            this.success = '';
            this.selectedApp = null;
            this.reviewForm = {comment: '', opinion: '', deadline: ''};
            try {
                if (key === 'notices') {
                    await this.loadNotices();
                } else if (key === 'myapps') {
                    await this.loadMyApps();
                } else if (key === 'publicity') {
                    await this.loadNotices();
                    await this.initPublicity();
                } else if (key === 'counselor') {
                    await this.loadCounselor();
                } else if (key === 'college') {
                    await this.loadCollege();
                } else if (key === 'affairs') {
                    await this.loadNotices();
                    await this.initAffairs();
                } else if (key === 'stats') {
                    await this.loadNotices();
                    if (!this.statsNoticeId && this.notices.length) {
                        this.statsNoticeId = this.notices[0].id;
                    }
                    await this.loadStats();
                }
            } catch (e) {
                this.notifyError(e.message);
            }
        },

        async loadNotices() {
            this.notices = await apiRequest('GET', '/notices');
            if (this.selectedNotice) {
                this.selectedNotice = this.notices.find(n => n.id === this.selectedNotice.id) || null;
            }
        },
        openNotice(notice) {
            this.selectedNotice = notice;
            this.applyForm = {reason: '', materials: []};
        },
        async submitApplication() {
            if (!this.applyForm.reason.trim()) {
                this.notifyError('请填写申请理由');
                return;
            }
            try {
                const result = await apiRequest('POST', '/applications', {
                    noticeId: this.selectedNotice.id,
                    reason: this.applyForm.reason,
                    materials: this.applyForm.materials
                });
                this.notifySuccess(result.message);
                this.applyForm = {reason: '', materials: []};
                await this.loadMyApps();
            } catch (e) {
                this.notifyError(e.message);
            }
        },
        async loadMyApps() {
            this.myApps = await apiRequest('GET', '/applications/mine');
            if (this.selectedApp) {
                this.selectedApp = this.myApps.find(a => a.id === this.selectedApp.id) || null;
            }
        },
        openMyApp(application) {
            this.selectedApp = application;
            this.resubmitForm = {
                reason: application.reason,
                materials: (application.materials || []).slice()
            };
        },
        async resubmit() {
            try {
                const result = await apiRequest('POST', `/applications/${this.selectedApp.id}/resubmit`, {
                    reason: this.resubmitForm.reason,
                    materials: this.resubmitForm.materials
                });
                this.notifySuccess(result.message);
                this.selectedApp = result.application;
                await this.loadMyApps();
            } catch (e) {
                this.notifyError(e.message);
            }
        },
        publicityEndOf(application) {
            const notice = this.notices.find(n => n.id === application.noticeId);
            return notice ? notice.publicityEnd : null;
        },
        async initPublicity() {
            if (!this.publicizedNotices.length) {
                this.publicData = null;
                return;
            }
            if (!this.publicNoticeId || !this.publicizedNotices.some(n => n.id === this.publicNoticeId)) {
                this.publicNoticeId = this.publicizedNotices[0].id;
            }
            await this.loadPublicList();
        },
        async loadPublicList() {
            if (!this.publicNoticeId) {
                this.publicData = null;
                return;
            }
            this.publicData = await apiRequest('GET', `/publicity/${this.publicNoticeId}`);
        },

        async loadCounselor() {
            this.counselorApps = await apiRequest('GET', '/counselor/applications');
            if (this.selectedApp) {
                const found = this.counselorApps.find(a => a.id === this.selectedApp.id);
                if (found) {
                    this.selectedApp = found;
                }
            }
        },
        selectApp(application) {
            this.selectedApp = application;
            this.reviewForm = {
                comment: '',
                opinion: '',
                deadline: toLocalInput(new Date(Date.now() + 30 * 60 * 1000))
            };
        },
        async counselorAction(action) {
            if (action === 'reject' && !this.reviewForm.comment.trim()) {
                this.notifyError('驳回时必须填写驳回理由');
                return;
            }
            try {
                const result = await apiRequest('POST',
                    `/applications/${this.selectedApp.id}/counselor-review`,
                    {action, comment: this.reviewForm.comment});
                this.notifySuccess(result.message);
                await this.loadCounselor();
                this.selectedApp = result.application;
                this.reviewForm.comment = '';
            } catch (e) {
                this.notifyError(e.message);
            }
        },
        async doCorrection() {
            if (!this.reviewForm.opinion.trim()) {
                this.notifyError('退补时必须填写补正意见');
                return;
            }
            if (!this.reviewForm.deadline) {
                this.notifyError('请设置补正截止时间');
                return;
            }
            try {
                const result = await apiRequest('POST',
                    `/applications/${this.selectedApp.id}/correction`,
                    {opinion: this.reviewForm.opinion, deadline: this.reviewForm.deadline});
                this.notifySuccess(result.message);
                await this.loadCounselor();
                this.selectedApp = result.application;
                this.reviewForm.opinion = '';
            } catch (e) {
                this.notifyError(e.message);
            }
        },
        async loadCollege() {
            this.collegeApps = await apiRequest('GET', '/college/applications');
            if (this.selectedApp) {
                const found = this.collegeApps.find(a => a.id === this.selectedApp.id);
                if (found) {
                    this.selectedApp = found;
                }
            }
        },
        async collegeAction(action) {
            if (action === 'reject' && !this.reviewForm.comment.trim()) {
                this.notifyError('驳回时必须填写驳回理由');
                return;
            }
            try {
                const result = await apiRequest('POST',
                    `/applications/${this.selectedApp.id}/college-review`,
                    {action, comment: this.reviewForm.comment});
                this.notifySuccess(result.message);
                await this.loadCollege();
                this.selectedApp = result.application;
                this.reviewForm.comment = '';
            } catch (e) {
                this.notifyError(e.message);
            }
        },

        async initAffairs() {
            if (!this.notices.length) {
                return;
            }
            if (!this.affairsNoticeId || !this.notices.some(n => n.id === this.affairsNoticeId)) {
                this.affairsNoticeId = this.notices[0].id;
            }
            await this.loadCandidates();
            if (this.publicizedNotices.length) {
                if (!this.adminNoticeId || !this.publicizedNotices.some(n => n.id === this.adminNoticeId)) {
                    this.adminNoticeId = this.publicizedNotices[0].id;
                }
                await this.loadAdminList();
            } else {
                this.adminData = null;
            }
        },
        async loadCandidates() {
            if (!this.affairsNoticeId) {
                this.candidates = [];
                return;
            }
            this.candidates = await apiRequest('GET', `/publicity/candidates/${this.affairsNoticeId}`);
            this.publishIds = this.candidates
                .filter(c => c.status === 'PENDING_PUBLICITY')
                .map(c => c.id);
            this.publishStart = toLocalInput(new Date());
            this.publishEnd = toLocalInput(new Date(Date.now() + 2 * 60 * 1000));
        },
        async publish() {
            if (!this.publishIds.length) {
                this.notifyError('请至少选择一条待公示记录');
                return;
            }
            if (!this.publishStart || !this.publishEnd) {
                this.notifyError('请设置公示起止时间');
                return;
            }
            try {
                const result = await apiRequest('POST', '/publicity/publish', {
                    noticeId: this.affairsNoticeId,
                    applicationIds: this.publishIds,
                    start: this.publishStart,
                    end: this.publishEnd
                });
                this.notifySuccess(result.message);
                await this.loadNotices();
                await this.loadCandidates();
                this.adminNoticeId = this.affairsNoticeId;
                await this.loadAdminList();
            } catch (e) {
                this.notifyError(e.message);
            }
        },
        async loadAdminList() {
            if (!this.adminNoticeId) {
                this.adminData = null;
                return;
            }
            const data = await apiRequest('GET', `/publicity/${this.adminNoticeId}/admin`);
            const items = {};
            data.list.filter(a => a.status === 'PUBLICIZING').forEach(a => {
                items[a.id] = {approved: null, reason: ''};
            });
            this.confirmItems = items;
            this.disputeHandled = false;
            this.adminData = data;
        },
        async confirmResults() {
            if (!this.adminPublicizing.length) {
                this.notifyError('该批次没有处于公示中的记录');
                return;
            }
            const items = [];
            for (const application of this.adminPublicizing) {
                const item = this.confirmItems[application.id] || {};
                if (item.approved === null || item.approved === undefined) {
                    this.notifyError(`请为 ${application.studentName} 选择“已获批”或“未获批”`);
                    return;
                }
                if (item.approved === false && !String(item.reason || '').trim()) {
                    this.notifyError(`未获批记录必须填写原因：${application.studentName}`);
                    return;
                }
                items.push({
                    applicationId: application.id,
                    approved: item.approved,
                    reason: item.reason || ''
                });
            }
            try {
                const result = await apiRequest('POST', `/publicity/${this.adminNoticeId}/confirm`, {
                    disputeHandled: this.disputeHandled,
                    items
                });
                this.notifySuccess(result.message);
                await this.loadNotices();
                await this.loadAdminList();
                await this.loadCandidates();
            } catch (e) {
                this.notifyError(e.message);
            }
        },
        async loadStats() {
            if (!this.statsNoticeId) {
                this.stats = null;
                return;
            }
            try {
                let path = `/stats?noticeId=${this.statsNoticeId}`;
                if (this.statsCollege.trim()) {
                    path += `&college=${encodeURIComponent(this.statsCollege.trim())}`;
                }
                this.stats = await apiRequest('GET', path);
            } catch (e) {
                this.notifyError(e.message);
            }
        }
    },

    async mounted() {
        if (this.currentUser) {
            await this.afterLogin();
        }
    }
});

app.component('app-detail', ApplicationDetail);
app.mount('#app');
