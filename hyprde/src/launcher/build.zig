const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const exe = b.addExecutable(.{
        .name = "hyprsearch",
        .root_module = b.createModule(.{
            .target = target,
            .optimize = optimize,
        }),
    });

    // Scrub absolute build paths from the binary (no usernames or machine
    // layout in public artifacts). Clang records source paths as given;
    // remap the build root to a stable placeholder.
    const src_root: []const u8 = b.build_root.path orelse ".";
    const prefix_map = b.fmt("-ffile-prefix-map={s}=hyprde-src", .{src_root});

    exe.root_module.addCSourceFile(.{ .file = b.path("src/launcher.c"), .flags = &.{prefix_map} });
    exe.root_module.addCSourceFile(.{ .file = b.path("src/toml.c"), .flags = &.{prefix_map} });
    exe.root_module.link_libc = true;
    exe.root_module.linkSystemLibrary("gtk+-3.0", .{});
    exe.root_module.linkSystemLibrary("gtk-layer-shell-0", .{});
    exe.root_module.linkSystemLibrary("gio-2.0", .{});

    b.installArtifact(exe);
}
