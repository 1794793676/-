package com.demo.scholarship.seed;

import com.demo.scholarship.domain.Notice;
import com.demo.scholarship.domain.User;
import com.demo.scholarship.domain.enums.Role;
import com.demo.scholarship.repo.NoticeRepository;
import com.demo.scholarship.repo.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

@Component
public class DataSeeder implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(DataSeeder.class);

    private final UserRepository userRepository;
    private final NoticeRepository noticeRepository;

    public DataSeeder(UserRepository userRepository, NoticeRepository noticeRepository) {
        this.userRepository = userRepository;
        this.noticeRepository = noticeRepository;
    }

    @Override
    public void run(String... args) {
        if (userRepository.count() > 0) {
            return;
        }

        User wang = user("wangls", "王老师", Role.COUNSELOR, null, "计算机学院");
        User liu = user("liuls", "刘老师", Role.COUNSELOR, null, "软件学院");
        userRepository.save(wang);
        userRepository.save(liu);

        userRepository.save(user("jsxy", "计算机学院审核员", Role.COLLEGE, null, "计算机学院"));
        userRepository.save(user("rjxy", "软件学院审核员", Role.COLLEGE, null, "软件学院"));
        userRepository.save(user("xsc", "学生处张老师", Role.AFFAIRS, null, null));

        student("zhang3", "张三", "202411701202", "计算机学院", wang);
        student("wangxm", "王小明", "202411701406", "计算机学院", wang);
        student("lisi", "李四", "202411701408", "软件学院", liu);

        LocalDateTime now = LocalDateTime.now();

        Notice n1 = new Notice();
        n1.setProjectName("国家励志奖学金");
        n1.setBatchName("2026年秋季批次");
        n1.setLevel("一等");
        n1.setConditions("全日制在校本科生，品学兼优且家庭经济困难，无违纪记录。");
        n1.setRequiredMaterials("成绩单,家庭经济困难证明,学籍证明");
        n1.setApplyStart(now.minusDays(1));
        n1.setApplyEnd(now.plusDays(7));
        n1.setPublished(true);
        noticeRepository.save(n1);

        Notice n2 = new Notice();
        n2.setProjectName("校级奖学金");
        n2.setBatchName("2025年春季批次");
        n2.setLevel("二等");
        n2.setConditions("上一学年综合测评排名前 30%，无课程不及格。");
        n2.setRequiredMaterials("成绩单,综合测评表");
        n2.setApplyStart(now.minusDays(30));
        n2.setApplyEnd(now.minusDays(1));
        n2.setPublished(true);
        noticeRepository.save(n2);

        Notice n3 = new Notice();
        n3.setProjectName("国家奖学金");
        n3.setBatchName("2026年秋季批次");
        n3.setLevel("特等");
        n3.setConditions("本年度学业成绩与综合表现特别优秀。");
        n3.setRequiredMaterials("成绩单,获奖证明");
        n3.setApplyStart(now);
        n3.setApplyEnd(now.plusDays(10));
        n3.setPublished(false);
        noticeRepository.save(n3);

        log.info("演示数据初始化完成：账号密码均为 123456（学生 zhang3/wangxm/lisi，辅导员 wangls/liuls，"
                + "学院审核员 jsxy/rjxy，学生处 xsc）");
    }

    private User user(String username, String name, Role role, String studentNo, String college) {
        User user = new User();
        user.setUsername(username);
        user.setPassword("123456");
        user.setName(name);
        user.setRole(role);
        user.setStudentNo(studentNo);
        user.setCollege(college);
        return user;
    }

    private void student(String username, String name, String studentNo, String college, User counselor) {
        User student = user(username, name, Role.STUDENT, studentNo, college);
        student.setCounselorId(counselor.getId());
        userRepository.save(student);
    }
}
